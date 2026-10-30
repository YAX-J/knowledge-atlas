"""Durable call reservations and validated partials, without provider traffic."""
import copy
from contextlib import nullcontext
from datetime import timedelta
import uuid
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from app.agents.runtime import RunContext, agent_scope, embedding_attempt, invoke_model, invoke_tool, run_scope
from app.core.errors import AppError
from app.core.identity import DEVELOPMENT_USER_ID
from app.models.agent_run import AgentRun
from app.models.domain import Project, utc_now
from app.services import agent_workflows, deepseek
from app.services.agent_progress import save_progress
from app.workflows.contracts import WorkflowRequest
from app.workflows.routing import PIPELINES
from tests.test_knowledge import configured
from tests.test_multi_agent import prepare
from tests.test_sources import create_project


def make_run(client, db):
    project = uuid.UUID(create_project(client))
    execution = uuid.uuid4()
    context = RunContext(user_id=DEVELOPMENT_USER_ID, project_id=project)
    db.add(AgentRun(id=context.run_id, user_id=context.user_id, project_id=project,
        kind='question_pipeline', status='running', input_sha256='0' * 64, request={},
        usage={}, events=[], execution_id=execution, lease_until=utc_now() + timedelta(seconds=60)))
    db.commit()
    return context, execution


def test_runtime_checkpoints_reservations_before_callbacks_and_excludes_content():
    snapshots = []
    context = RunContext(user_id=uuid.uuid4(), project_id=uuid.uuid4(),
        on_progress=lambda value: snapshots.append(copy.deepcopy((value.events, value.usage()))))
    def provider():
        events, usage = snapshots[-1]
        assert usage['model'] == 1 and events[-1]['kind'] == 'model'
        assert events[-1]['status'] == 'started'
        raise ValueError('private provider response')
    with run_scope(context), agent_scope('evidence_qa'):
        with pytest.raises(ValueError):
            invoke_model(provider)
        with pytest.raises(ValueError):
            invoke_tool(lambda *_: (_ for _ in ()).throw(ValueError('private arguments')), 'read_evidence')
        embedding_attempt()
    assert context.counts == {'model': 1, 'tool': 1, 'embedding': 1}
    assert any(event['kind'] == 'tool' and event['status'] == 'failed' for event in context.events)
    assert 'private' not in str(snapshots)


def test_persistence_failure_stops_later_calls_and_restores_role_context():
    def unavailable(_context):
        raise RuntimeError('private database connection')
    context = RunContext(user_id=uuid.uuid4(), project_id=uuid.uuid4(), on_progress=unavailable)
    with run_scope(context):
        with pytest.raises(AppError) as failure:
            with agent_scope('code_analysis'):
                pytest.fail('Failed checkpoint must prevent agent work')
        assert failure.value.code == 'WORKFLOW_PROGRESS_UNAVAILABLE'
        assert 'private' not in failure.value.message
        with pytest.raises(AppError):
            invoke_model(lambda: pytest.fail('Must not call a provider after progress failure'))
        context.event('workflow', 'failed')
    assert context.events[-1]['agent'] == 'workflow'
    assert context.counts['model'] == 0


def test_progress_commit_saves_metadata_and_partial_without_mutating_source_data(client, db_session):
    context, execution = make_run(client, db_session)
    context.event('workflow', 'started')
    context.reserve('model')
    save_progress(db_session, context=context, execution_id=execution, result={'code_analysis': {'calls': []}})
    db_session.rollback()
    db_session.expire_all()
    record = db_session.get(AgentRun, context.run_id)
    assert record.status == 'running' and record.usage['model'] == 1
    assert record.events[-1]['kind'] == 'model'
    assert record.result == {'code_analysis': {'calls': []}}
    assert agent_workflows.aware(record.lease_until) > utc_now() + timedelta(seconds=1100)


@pytest.mark.parametrize('boundary', ['user', 'project', 'execution', 'expired', 'finished', 'archived'])
def test_progress_rejects_foreign_or_abandoned_ownership(client, db_session, boundary):
    context, execution = make_run(client, db_session)
    if boundary == 'user': context.user_id = uuid.uuid4()
    if boundary == 'project': context.project_id = uuid.uuid4()
    if boundary == 'execution': execution = uuid.uuid4()
    record = db_session.get(AgentRun, context.run_id)
    if boundary == 'expired': record.lease_until = utc_now() - timedelta(seconds=1)
    if boundary == 'finished': record.status = 'failed'
    if boundary == 'archived': db_session.get(Project, record.project_id).archived_at = utc_now()
    db_session.commit()
    with pytest.raises(AppError) as failure:
        save_progress(db_session, context=context, execution_id=execution)
    assert failure.value.code == 'WORKFLOW_INTERRUPTED'
    assert db_session.get(AgentRun, context.run_id).usage == {}


def test_progress_never_commits_pending_business_writes(client, db_session):
    context, execution = make_run(client, db_session)
    project = db_session.get(Project, context.project_id)
    original = project.name
    project.name = 'Unfinished mutation'
    with pytest.raises(AppError) as failure:
        save_progress(db_session, context=context, execution_id=execution)
    assert failure.value.code == 'WORKFLOW_PROGRESS_UNAVAILABLE'
    db_session.rollback()
    assert db_session.get(Project, context.project_id).name == original
    assert db_session.get(AgentRun, context.run_id).usage == {}


def test_progress_storage_errors_are_sanitized_and_rolled_back():
    db = Mock(new=set(), dirty=set(), deleted=set())
    db.no_autoflush = nullcontext()
    db.execute.side_effect = RuntimeError('private database URL')
    context = RunContext(user_id=uuid.uuid4(), project_id=uuid.uuid4())
    with pytest.raises(AppError) as failure:
        save_progress(db, context=context, execution_id=uuid.uuid4())
    assert failure.value.code == 'WORKFLOW_PROGRESS_UNAVAILABLE'
    assert 'private' not in failure.value.message
    db.rollback.assert_called_once()


def test_provider_observes_already_persisted_reservation(client, db_session, configured, monkeypatch):
    project, source, _draft, seen = prepare(client, monkeypatch, configured)
    original = deepseek.call_agent_turn
    identifier = uuid.uuid4()
    reservations = []
    def observe(*args, **kwargs):
        usage, events = db_session.execute(select(AgentRun.usage, AgentRun.events).where(AgentRun.id == identifier)).one()
        reservations.append((copy.deepcopy(usage), copy.deepcopy(events)))
        assert events[-1]['kind'] == 'model' and events[-1]['status'] == 'started'
        return original(*args, **kwargs)
    monkeypatch.setattr('app.services.deepseek.call_agent_turn', observe)
    response = client.post(f'/api/v1/projects/{project}/agent-runs', json=dict(
        request_id=str(identifier), kind='knowledge_pipeline', source_id=source['source_id']))
    assert response.status_code == 200, response.text
    assert [usage['model'] for usage, _events in reservations] == [1, 2]
    assert len(seen) == 2
    assert any(event['kind'] == 'extraction_checkpoint' for event in response.json()['events'])


def test_crash_after_extraction_keeps_candidates_and_usage_without_paid_replay(client, db_session, configured, monkeypatch):
    project, source, _draft, seen = prepare(client, monkeypatch, configured)
    original = PIPELINES['knowledge_pipeline']
    class ProcessStopped(BaseException): pass
    def interrupted(code, extract):
        original(code, extract)
        raise ProcessStopped()
    monkeypatch.setitem(PIPELINES, 'knowledge_pipeline', interrupted)
    request = WorkflowRequest(request_id=uuid.uuid4(), kind='knowledge_pipeline', source_id=source['source_id'])
    with pytest.raises(ProcessStopped):
        agent_workflows.start_run(db_session, user_id=DEVELOPMENT_USER_ID,
            project_id=uuid.UUID(project), request=request, settings=configured)
    db_session.rollback()
    db_session.expire_all()
    record = db_session.get(AgentRun, request.request_id)
    assert record.result['status'] == 'awaiting_review' and len(record.result['candidate_ids']) == 3
    assert record.usage['model'] == 2 and len(seen) == 2
    record.lease_until = utc_now() - timedelta(seconds=1)
    db_session.commit()
    url = f'/api/v1/projects/{project}/agent-runs'
    read = client.get(f'{url}/{request.request_id}').json()
    assert read['status'] == 'interrupted' and read['review_counts'] == {'pending': 3}
    assert client.post(url, json=request.model_dump(mode='json')).json() == read
    assert len(seen) == 2


def test_expired_progress_stops_after_the_first_provider_call(client, db_session, configured, monkeypatch):
    project, source, _draft, _seen = prepare(client, monkeypatch, configured)
    identifier = uuid.uuid4()
    calls = []
    def expire(*_args, **_kwargs):
        calls.append(1)
        record = db_session.get(AgentRun, identifier)
        record.lease_until = utc_now() - timedelta(seconds=1)
        db_session.commit()
        return {'content': 'This response must not start another call'}
    monkeypatch.setattr('app.services.deepseek.call_agent_turn', expire)
    body = dict(request_id=str(identifier), kind='knowledge_pipeline', source_id=source['source_id'])
    url = f'/api/v1/projects/{project}/agent-runs'
    assert client.post(url, json=body).status_code == 409
    read = client.get(f'{url}/{identifier}').json()
    assert read['status'] == 'interrupted' and read['usage']['model'] == 1
    assert client.post(url, json=body).json() == read and len(calls) == 1


def test_failed_call_reservation_never_sends_a_model_request(client, configured, monkeypatch):
    project, source, _draft, seen = prepare(client, monkeypatch, configured)
    original = agent_workflows.save_progress
    def fail_reservation(db, **kwargs):
        if kwargs['context'].events[-1]['kind'] == 'model':
            raise RuntimeError('private connection details')
        return original(db, **kwargs)
    monkeypatch.setattr(agent_workflows, 'save_progress', fail_reservation)
    body = dict(request_id=str(uuid.uuid4()), kind='knowledge_pipeline', source_id=source['source_id'])
    url = f'/api/v1/projects/{project}/agent-runs'
    result = client.post(url, json=body)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['status'] == 'failed' and data['error_code'] == 'WORKFLOW_PROGRESS_UNAVAILABLE'
    assert not seen and 'private' not in str(data)
    assert client.post(url, json=body).json() == data and not seen


def test_crash_after_validated_answer_keeps_readable_result(client, db_session, configured, monkeypatch):
    from app.api.routes import agents as routes
    project = create_project(client)
    monkeypatch.setattr(routes, 'get_settings', lambda: configured)
    original = PIPELINES['question_pipeline']
    class ProcessStopped(BaseException): pass
    def interrupted(code, answer):
        original(code, answer)
        raise ProcessStopped()
    monkeypatch.setitem(PIPELINES, 'question_pipeline', interrupted)
    request = WorkflowRequest(request_id=uuid.uuid4(), kind='question_pipeline', question='Unknown')
    with pytest.raises(ProcessStopped):
        agent_workflows.start_run(db_session, user_id=DEVELOPMENT_USER_ID,
            project_id=uuid.UUID(project), request=request, settings=configured)
    db_session.rollback()
    db_session.expire_all()
    record = db_session.get(AgentRun, request.request_id)
    assert record.result['answer']['supported'] is False and record.usage['model'] == 0
    assert record.events[-1]['kind'] == 'answer_checkpoint'
    record.lease_until = utc_now() - timedelta(seconds=1)
    db_session.commit()
    read = client.get(f'/api/v1/projects/{project}/agent-runs/{request.request_id}').json()
    assert read['status'] == 'interrupted' and read['result']['answer'] == record.result['answer']
