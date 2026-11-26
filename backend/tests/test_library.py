import copy
import uuid
from datetime import timedelta

from sqlalchemy import func, select

from app.api.dependencies import get_current_user_id
from app.main import app
from app.models.assistant_task import AssistantTask
from app.models.domain import Project, SourceDocument, utc_now
from app.models.agent_run import AgentRun
from app.models.library import AnswerFeedback, SourceArchive
from app.models.workspace import ConversationTurn
from tests.test_sources import create_project
from tests.test_parsing import upload


def test_project_edit_conflict_archive_restore_and_scope(client, db_session):
    project = client.post('/api/v1/projects', json={'name':'Original'}).json()
    url = '/api/v1/projects/' + project['id']
    request = dict(name='Renamed', description='Retained history', expected_updated_at=project['updated_at'])
    edited = client.put(url, json=request)
    assert edited.status_code == 200
    assert edited.json()['name'] == 'Renamed'
    assert client.put(url, json=request).json() == edited.json()
    assert client.put(url, json={**request, 'name':'Stale overwrite'}).status_code == 409
    archived = client.put(url+'/archive', json={'archived':True, 'expected_updated_at':edited.json()['updated_at']})
    assert archived.status_code == 200
    assert project['id'] not in {item['id'] for item in client.get('/api/v1/projects?page_size=100').json()['items']}
    assert client.get(url).status_code == 404
    assert client.get(url+'/graph').status_code == 404
    assert project['id'] in {item['id'] for item in client.get('/api/v1/projects?archived=true&page_size=100').json()['items']}
    assert db_session.get(Project, uuid.UUID(project['id'])).name == 'Renamed'
    restored = client.put(url+'/archive', json={'archived':False, 'expected_updated_at':archived.json()['updated_at']})
    assert restored.status_code == 200
    assert client.get(url).json()['description'] == 'Retained history'
    app.dependency_overrides[get_current_user_id] = lambda:uuid.uuid4()
    try:
        assert client.put(url, json=request).status_code == 404
        assert client.put(url+'/archive', json={'archived':True,'expected_updated_at':restored.json()['updated_at']}).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)


def test_project_archive_refuses_queued_assistant(client, db_session):
    project = client.post('/api/v1/projects', json={'name':'Busy'}).json()
    record = db_session.get(Project,uuid.UUID(project['id']))
    db_session.add(AssistantTask(id=uuid.uuid4(),user_id=record.user_id,project_id=record.id,
        status='queued',input_sha256='a'*64,request={}))
    db_session.commit()
    response = client.put(f"/api/v1/projects/{record.id}/archive",json={'archived':True,'expected_updated_at':project['updated_at']})
    assert response.status_code == 409 and response.json()['error']['code'] == 'PROJECT_BUSY'
    assert client.get(f'/api/v1/projects/{record.id}').status_code == 200


def test_project_archive_allows_an_expired_legacy_workflow(client, db_session):
    project=client.post('/api/v1/projects',json={'name':'Expired workflow'}).json()
    record=db_session.get(Project,uuid.UUID(project['id']))
    db_session.add(AgentRun(id=uuid.uuid4(),user_id=record.user_id,project_id=record.id,kind='question',
        status='running',input_sha256='a'*64,request={},lease_until=utc_now()-timedelta(minutes=5)))
    db_session.commit()
    response=client.put(f'/api/v1/projects/{record.id}/archive',json={'archived':True,'expected_updated_at':project['updated_at']})
    assert response.status_code == 200,response.text


def test_source_archive_preserves_exact_chunks_dedup_and_reversible_listing(client, db_session):
    project = create_project(client)
    source = upload(client,project)
    assert client.post(f"/api/v1/tasks/{source['task_id']}/run").status_code == 200
    chunks_url=f"/api/v1/sources/{source['source_id']}/chunks"
    chunks=client.get(chunks_url).json()
    url=f"/api/v1/projects/{project}/sources/{source['source_id']}/archive"
    assert client.put(url,json={'archived':True,'reason':'Move out of daily library'}).status_code == 200
    assert client.put(url,json={'archived':True,'reason':'Idempotent repeat'}).status_code == 200
    assert db_session.scalar(select(func.count()).select_from(SourceArchive)) == 1
    assert client.get(f'/api/v1/projects/{project}/sources').json()['total'] == 0
    archived=client.get(f'/api/v1/projects/{project}/sources?archived=true').json()
    assert archived['total'] == 1 and archived['items'][0]['archived'] is True
    assert client.get(f"/api/v1/sources/{source['source_id']}").json()['archived'] is True
    assert client.get(chunks_url).json() == chunks
    chunk=chunks['items'][0]
    assert client.get(f"/api/v1/projects/{project}/sources/{source['source_id']}/chunks/{chunk['id']}").status_code == 200
    assert upload(client,project)['source_id'] == source['source_id']
    assert client.get(f'/api/v1/projects/{project}/sources').json()['total'] == 0
    foreign=create_project(client)
    assert client.put(url.replace(project,foreign),json={'archived':False,'reason':'Wrong project'}).status_code == 404
    assert client.put(url,json={'archived':False,'reason':'Restore'}).json()['archived'] is False
    assert client.get(f'/api/v1/projects/{project}/sources').json()['total'] == 1


def test_source_archive_excludes_default_symbol_search(client):
    project=create_project(client)
    result=client.post(f'/api/v1/projects/{project}/sources',files={'file':('utility.py',b'def unique_function():\n    return 1\n','text/x-python')}).json()
    client.post(f"/api/v1/tasks/{result['task_id']}/run")
    url=f'/api/v1/projects/{project}/code-symbols?q=unique_function'
    assert client.get(url).json()['items']
    client.put(f"/api/v1/projects/{project}/sources/{result['source_id']}/archive",json={'archived':True,'reason':'Archived code'})
    assert client.get(url).json()['items'] == []


def saved_turn(client):
    project=create_project(client)
    conversation=client.post(f'/api/v1/projects/{project}/conversations',json={}).json()
    response=client.post(f"/api/v1/projects/{project}/conversations/{conversation['id']}/turns",json={
        'request_id':str(uuid.uuid4()),'question':'What is known?','retrieval_mode':'bm25'})
    assert response.status_code == 200,response.text
    return project,response.json()


def test_feedback_is_bound_to_saved_claim_and_idempotent_without_rewriting_answer(client,db_session):
    project,turn=saved_turn(client)
    original=copy.deepcopy(turn['answer'])
    url=f"/api/v1/projects/{project}/answers/{turn['id']}/feedback"
    request=dict(request_id=str(uuid.uuid4()),claim_index=0,category='incomplete',comment='Please add more evidence.')
    response=client.post(url,json=request)
    assert response.status_code == 201,response.text
    assert response.json()['claim_text'] == original['claims'][0]['text']
    assert len(response.json()['answer_sha256']) == 64
    assert client.post(url,json=request).json() == response.json()
    assert client.post(url,json={**request,'comment':'Changed'}).status_code == 409
    assert client.post(url,json={**request,'request_id':str(uuid.uuid4()),'claim_index':1}).status_code == 422
    assert len(client.get(url).json()) == 1
    assert db_session.get(ConversationTurn,uuid.UUID(turn['id'])).answer == original
    assert db_session.scalar(select(func.count()).select_from(AnswerFeedback)) == 1
    foreign=create_project(client)
    assert client.get(url.replace(project,foreign)).status_code == 404
    assert client.post(url.replace(project,foreign),json=request).status_code == 404
    app.dependency_overrides[get_current_user_id]=lambda:uuid.uuid4()
    try:
        assert client.get(url).status_code == 404
        assert client.post(url,json=request).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)
