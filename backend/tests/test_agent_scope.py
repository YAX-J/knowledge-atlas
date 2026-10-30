"""Saved workflow scope is allowlisted and retains explicit immutable selections."""
from datetime import datetime
import uuid

import pytest
from sqlalchemy import func, select

from app.api.routes import agents as routes
from app.core.config import Settings
from app.models.agent_run import AgentRun
from app.services import deepseek
from tests.test_code_context import prepare
from tests.test_knowledge import configured
from tests.test_sources import create_project


def test_history_scope_survives_reads_without_exposing_raw_request(client, monkeypatch):
    project=create_project(client)
    monkeypatch.setattr(routes,'get_settings',lambda:Settings(_env_file=None))
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_k:pytest.fail('Empty evidence must not call providers'))
    body=dict(request_id=str(uuid.uuid4()),kind='question_pipeline',question='Unknown historical fact',
        retrieval_mode='bm25_source',valid_at='2026-10-01T10:30:00+08:00')
    url=f'/api/v1/projects/{project}/agent-runs'
    response=client.post(url,json=body)
    assert response.status_code==200,response.text
    data=response.json();scope=data['scope']
    assert scope['retrieval_mode']=='bm25_source' and not scope['include_code_analysis']
    assert datetime.fromisoformat(scope['valid_at'])==datetime.fromisoformat(body['valid_at'])
    assert set(scope)=={'retrieval_mode','valid_at','include_code_analysis','code_strategy','snapshot_id','version_ids'}
    assert 'request' not in data and 'source_sha256' not in str(scope)
    assert client.get(f"{url}/{data['id']}").json()['scope']==scope
    assert client.get(url).json()['items'][0]['scope']==scope
    assert client.post(url,json=body).json()==data


def test_workflow_forwards_and_reports_explicit_local_versions(client,monkeypatch,configured):
    project,_repository,old,_new,main,captured=prepare(client,monkeypatch)
    monkeypatch.setattr(routes,'get_settings',lambda:configured)
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_k:pytest.fail('Static analysis and empty QA must be free'))
    body=dict(request_id=str(uuid.uuid4()),kind='question_pipeline',source_id=main['source_id'],
        question='Unknown',include_code_analysis=True,code_strategy='semantic',version_ids=[old['source_id']])
    response=client.post(f'/api/v1/projects/{project}/agent-runs',json=body)
    assert response.status_code==200,response.text
    data=response.json()
    assert data['status']=='succeeded' and data['usage']['model']==0
    assert str(captured[-1][1][0].id)==old['source_id']
    assert data['scope']['version_ids']==[old['source_id']] and data['scope']['code_strategy']=='semantic'
    assert data['scope']['snapshot_id'] is None


@pytest.mark.parametrize('change',[{'valid_at':'2026-10-01T10:30:00'},
    {'valid_at':'2026-10-01T10:30:00Z','include_code_analysis':True,'source_id':str(uuid.uuid4())},
    {'include_code_analysis':True,'source_id':str(uuid.uuid4()),'snapshot_id':str(uuid.uuid4()),'version_ids':[str(uuid.uuid4())]}])
def test_invalid_time_and_mixed_scope_are_rejected_before_execution(client,db_session,monkeypatch,change):
    project=create_project(client)
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_k:pytest.fail('Invalid scope must be free'))
    response=client.post(f'/api/v1/projects/{project}/agent-runs',json=dict(
        request_id=str(uuid.uuid4()),kind='question_pipeline',question='Unknown',**change))
    assert response.status_code==422,response.text
    assert db_session.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.project_id==uuid.UUID(project)))==0


def test_unconfigured_selected_mode_is_preserved_in_failed_task_scope(client,monkeypatch):
    project=create_project(client)
    monkeypatch.setattr(routes,'get_settings',lambda:Settings(_env_file=None))
    response=client.post(f'/api/v1/projects/{project}/agent-runs',json=dict(request_id=str(uuid.uuid4()),
        kind='question_pipeline',question='Unknown',retrieval_mode='rrf'))
    assert response.status_code==200,response.text
    data=response.json()
    assert data['status']=='failed' and data['error_code']=='EMBEDDING_NOT_CONFIGURED'
    assert data['scope']['retrieval_mode']=='rrf'
