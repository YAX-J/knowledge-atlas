"""Bounded workflow reads over synthetic envelopes; no providers or graph writes."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import event, func, select, update

from app.core.errors import AppError
from app.core.identity import DEVELOPMENT_USER_ID as USER
from app.models.agent_run import AgentRun
from app.models.domain import CandidateKnowledge, ProcessingTask, Project, SourceDocument
from app.services import agent_workflows as workflows, deepseek, embeddings
from app.services.projects import get_project


NOW = datetime(2026, 10, 30, 10, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def local_reads_only(monkeypatch):
    monkeypatch.setattr(workflows, 'utc_now', lambda: NOW)
    def forbidden(*_args, **_kwargs):
        pytest.fail('Workflow reads must never invoke providers')
    for name in ('answer_question', 'extract_candidates', 'call_agent_turn'):
        monkeypatch.setattr(deepseek, name, forbidden)
    monkeypatch.setattr(embeddings, 'embed_texts', forbidden)


def scope(db, *, project=None, user_id=USER):
    if project is None:
        project = Project(user_id=user_id, name='Synthetic list-performance scope')
        db.add(project); db.flush()
    source = SourceDocument(user_id=user_id, project_id=project.id, original_name='counts.md',
        media_type='text/markdown', source_type='markdown', size_bytes=7,
        content_sha256=uuid.uuid4().hex * 2, content='Fixture', status='ready')
    db.add(source); db.flush()
    task = ProcessingTask(user_id=user_id, project_id=project.id, source_id=source.id,
        type='knowledge_candidates', status='succeeded')
    db.add(task); db.flush()
    candidates = [CandidateKnowledge(user_id=user_id, project_id=project.id,
        source_id=source.id, task_id=task.id, candidate_type='Concept', name='Synthetic count',
        confidence=.8, payload={'fixture': 'not loaded for counts'}, review_status=status)
        for status in ('pending', 'confirmed', 'rejected')]
    db.add_all(candidates); db.flush()
    return project, source, task, candidates


def run(db, context, *, identifiers=None, **changes):
    project, source, task, candidates = context
    record = AgentRun(id=uuid.uuid4(), user_id=project.user_id, project_id=project.id,
        source_id=source.id, kind='knowledge_pipeline', status='awaiting_review',
        input_sha256='a'*64, request={'source_sha256': 'private-request-marker'},
        result={'extraction_task_id': str(task.id),
            'candidate_ids': identifiers if identifiers is not None else [str(item.id) for item in candidates]},
        events=[], usage={'model': 2}, created_at=NOW, updated_at=NOW)
    for key, value in changes.items():
        setattr(record, key, value)
    db.add(record)
    return record


@contextmanager
def selects(db):
    statements = []
    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)
    engine = db.get_bind()
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        yield statements
    finally:
        event.remove(engine, 'before_cursor_execute', capture)


def legacy_page(db, project_id, size):
    """Original list path retained in the test as an output/query-count reference."""
    get_project(db, user_id=USER, project_id=project_id)
    query = select(AgentRun).where(AgentRun.user_id == USER, AgentRun.project_id == project_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = list(db.scalars(query.order_by(AgentRun.created_at.desc(), AgentRun.id).limit(size)))
    return total, [workflows.read_run(db, user_id=USER, project_id=project_id,
        run_id=item.id).model_dump(mode='json') for item in items]


@pytest.mark.parametrize('size', [1, 10, 50])
def test_list_query_count_is_constant_and_full_output_matches_legacy(db_session, size):
    context = scope(db_session)
    project_id = context[0].id
    for _ in range(53): run(db_session, context)
    db_session.commit(); db_session.expunge_all()
    with selects(db_session) as before:
        total, expected = legacy_page(db_session, project_id, size)
    db_session.expunge_all()
    with selects(db_session) as after:
        result = workflows.list_runs(db_session, user_id=USER, project_id=project_id, page=1, page_size=size)
    assert result.total == total == 53 and len(result.items) == size
    assert [item.model_dump(mode='json') for item in result.items] == expected
    assert len(before) == 3 + 3 * size
    assert len(after) == 4
    candidate_query = next(sql for sql in after if 'candidate_knowledge' in sql)
    assert not any(f'candidate_knowledge.{name}' in candidate_query for name in ('payload', 'summary', 'name'))


def test_pagination_keeps_tied_timestamp_order_total_and_empty_page(db_session):
    context = scope(db_session)
    records = [run(db_session, context) for _ in range(53)]
    expected = sorted(item.id for item in records)
    project_id = context[0].id
    db_session.commit(); db_session.expunge_all()
    pages = [workflows.list_runs(db_session, user_id=USER, project_id=project_id,
        page=number, page_size=20) for number in range(1, 5)]
    assert [page.total for page in pages] == [53]*4
    assert [len(page.items) for page in pages] == [20, 20, 13, 0]
    assert [item.id for page in pages for item in page.items] == expected
    with selects(db_session) as statements:
        empty = workflows.list_runs(db_session, user_id=USER, project_id=project_id, page=4, page_size=20)
    assert not empty.items and len(statements) == 3


def test_counts_match_each_exact_id_subset_source_task_user_and_project(db_session):
    current = scope(db_session)
    other_source = scope(db_session, project=current[0])
    other_project = scope(db_session)
    foreign = scope(db_session, user_id=uuid.uuid4())
    project_id = current[0].id
    a, b, c = [str(item.id) for item in current[3]]
    all_ids = [a, b, c, str(other_source[3][0].id), str(other_project[3][0].id),
        str(foreign[3][0].id), str(uuid.uuid4()), a]
    first = run(db_session, current, identifiers=all_ids)
    second = run(db_session, current, identifiers=[b, c])
    third = run(db_session, current, identifiers=[a, a])
    wrong_source = run(db_session, current, source_id=other_source[1].id)
    another_task = ProcessingTask(user_id=USER, project_id=project_id, source_id=current[1].id,
        type='knowledge_candidates', status='succeeded')
    db_session.add(another_task); db_session.flush()
    wrong_task = run(db_session, current, result={'extraction_task_id': str(another_task.id), 'candidate_ids': [a,b,c]})
    outside = run(db_session, other_project)
    foreign_run = run(db_session, foreign)
    db_session.commit()
    result = workflows.list_runs(db_session, user_id=USER, project_id=project_id, page=1, page_size=50)
    by_id = {item.id: item for item in result.items}
    assert set(by_id) == {first.id, second.id, third.id, wrong_source.id, wrong_task.id}
    assert outside.id not in by_id and foreign_run.id not in by_id
    assert by_id[first.id].review_counts == {'pending':1, 'confirmed':1, 'rejected':1}
    assert by_id[second.id].review_counts == {'confirmed':1, 'rejected':1}
    assert by_id[third.id].review_counts == {'pending':1}
    assert by_id[wrong_source.id].review_counts == by_id[wrong_task.id].review_counts == {}
    for item in result.items:
        assert item.model_dump() == workflows.read_run(db_session, user_id=USER,
            project_id=project_id, run_id=item.id).model_dump()


@pytest.mark.parametrize('size', [0, 12])
def test_no_candidates_skip_review_query(db_session, size):
    context = scope(db_session)
    project_id = context[0].id
    shapes = [None, {}, {'candidate_ids': []}, {'code_analysis': {'synthetic': True}}]
    for index in range(size): run(db_session, context, result=shapes[index % len(shapes)])
    db_session.commit(); db_session.expunge_all()
    with selects(db_session) as statements:
        result = workflows.list_runs(db_session, user_id=USER, project_id=project_id, page=1, page_size=50)
    assert len(result.items) == size and len(statements) == 3
    assert all(item.review_counts == {} for item in result.items)


def test_leases_partial_results_and_saved_scope_are_read_only(db_session):
    context = scope(db_session)
    project_id = context[0].id
    states = [('running', None, 'interrupted'), ('running', NOW, 'interrupted'),
        ('running', NOW-timedelta(seconds=1), 'interrupted'),
        ('running', NOW+timedelta(minutes=1), 'running'),
        ('awaiting_review', None, 'awaiting_review'), ('failed', None, 'failed'),
        ('succeeded', None, 'succeeded'), ('interrupted', None, 'interrupted')]
    records = [run(db_session, context, status=status, lease_until=lease,
        request={'include_code_analysis': True, 'code_strategy':'tools', 'version_ids':[str(uuid.uuid4())],
            'source_sha256':'private-request-marker'}) for status, lease, _expected in states]
    db_session.commit()
    with selects(db_session):
        result = workflows.list_runs(db_session, user_id=USER, project_id=project_id, page=1, page_size=50)
    by_id = {item.id:item for item in result.items}
    for record, (status, _lease, expected) in zip(records, states):
        read = by_id[record.id]
        assert read.status == expected and record.status == status
        assert read.result == record.result and read.usage == record.usage and read.events == record.events
        assert read.review_counts == {'pending':1,'confirmed':1,'rejected':1}
        assert read.scope.include_code_analysis and read.scope.code_strategy == 'tools'
        assert read.model_dump() == workflows.read_run(db_session, user_id=USER,
            project_id=project_id, run_id=record.id).model_dump()
        assert 'private-request-marker' not in read.model_dump_json()
    assert not db_session.dirty and not db_session.new


def test_page_refreshes_cached_envelope_and_candidate_status(db_session):
    context = scope(db_session)
    project_id = context[0].id
    record = run(db_session, context, kind='question_pipeline')
    db_session.commit()
    db_session.execute(update(AgentRun).where(AgentRun.id==record.id).values(status='failed',
        request={'retrieval_mode':'bm25_source','valid_at':NOW.isoformat()},usage={'model':3},
        error_code='SYNTHETIC_FAILURE').execution_options(synchronize_session=False))
    db_session.execute(update(CandidateKnowledge).where(CandidateKnowledge.id==context[3][0].id)
        .values(review_status='rejected').execution_options(synchronize_session=False))
    db_session.commit()
    assert record.status == 'awaiting_review'
    result = workflows.list_runs(db_session, user_id=USER, project_id=project_id, page=1, page_size=50).items[0]
    assert result.status == 'failed' and result.usage == {'model':3} and result.error_code == 'SYNTHETIC_FAILURE'
    assert result.review_counts == {'confirmed':1,'rejected':2}
    assert result.scope.retrieval_mode == 'bm25_source' and result.scope.valid_at == NOW


def test_http_pagination_bounds_and_inaccessible_projects(client, db_session):
    current = scope(db_session)
    foreign = scope(db_session, user_id=uuid.uuid4())
    record = run(db_session, current)
    db_session.commit()
    base=f'/api/v1/projects/{current[0].id}/agent-runs'
    response=client.get(base)
    assert response.status_code==200 and response.json()['items'][0]['id']==str(record.id)
    assert response.json()['page']==1 and response.json()['page_size']==10
    for query in ('?page=0','?page_size=0','?page_size=51'):
        assert client.get(base+query).status_code==422
    for project_id in (foreign[0].id,uuid.uuid4()):
        assert client.get(f'/api/v1/projects/{project_id}/agent-runs').status_code==404
    with pytest.raises(AppError) as error:
        workflows.list_runs(db_session,user_id=uuid.uuid4(),project_id=current[0].id,page=1,page_size=10)
    assert error.value.code=='PROJECT_NOT_FOUND'
    current[0].archived_at=NOW
    db_session.commit()
    assert client.get(base).status_code==404
