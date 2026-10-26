import uuid
from app.api.routes import conversations as routes
from app.schemas.questions import AnswerDraft
from app.services import deepseek
from tests.test_questions import prepared_project
from tests.test_knowledge import configured


def test_persistent_conversation_idempotence_followups_and_project_boundary(client, configured, monkeypatch):
    project, settings = prepared_project(client, monkeypatch)
    monkeypatch.setattr(routes, 'get_settings', lambda:settings)
    calls=[]
    def answer(_settings, question, evidence, **kwargs):
        calls.append(kwargs.get('context'))
        return AnswerDraft(supported=True, answer='PostgreSQL stores the knowledge.', confidence=.9,
            citation_ids=[evidence[0]['id']], missing_information=[])
    monkeypatch.setattr(deepseek,'answer_question',answer)
    base=f'/api/v1/projects/{project}/conversations'
    conversation=client.post(base,json={}).json()
    path=base+f"/{conversation['id']}/turns"
    body=dict(request_id=str(uuid.uuid4()),question='Which database is used?',retrieval_mode='vector')
    first=client.post(path,json=body)
    assert first.status_code==200,first.text
    assert first.json()['status']=='succeeded'
    assert client.post(path,json=body).json()==first.json() and len(calls)==1
    assert client.post(path,json={**body,'question':'changed'}).status_code==409
    second=client.post(path,json={**body,'request_id':str(uuid.uuid4()),'question':'Why use it?'})
    assert second.status_code==200,second.text
    assert calls[-1][0]['question']==body['question']
    assert client.get(path).json()['total']==2
    assert client.get(base).json()['items'][0]['title']==body['question']
    other=client.post('/api/v1/projects',json={'name':'Other'}).json()['id']
    assert client.get(f"/api/v1/projects/{other}/conversations/{conversation['id']}/turns").status_code==404


def test_empty_conversation_refuses_without_provider_and_history_is_retained(client, monkeypatch):
    from app.core.config import Settings
    monkeypatch.setattr(routes,'get_settings',lambda:Settings(_env_file=None))
    monkeypatch.setattr(deepseek,'answer_question',lambda *_a,**_k: (_ for _ in ()).throw(AssertionError('no provider')))
    project=client.post('/api/v1/projects',json={'name':'Empty'}).json()['id']
    base=f'/api/v1/projects/{project}/conversations'
    conversation=client.post(base,json={}).json()
    path=base+f"/{conversation['id']}/turns"
    result=client.post(path,json=dict(request_id=str(uuid.uuid4()),question='What is known?',retrieval_mode='bm25'))
    assert result.status_code==200,result.text
    assert result.json()['answer']['supported'] is False
    assert client.get(path).json()['items'][0]['answer']==result.json()['answer']


def test_abandoned_execution_cannot_publish_into_retry_of_same_request(client, db_session, configured, monkeypatch):
    from app.models.workspace import Conversation
    project,settings=prepared_project(client,monkeypatch)
    monkeypatch.setattr(routes,'get_settings',lambda:settings)
    base=f'/api/v1/projects/{project}/conversations'
    conversation=client.post(base,json={}).json()
    path=base+f"/{conversation['id']}/turns"
    def abandoned(_settings,question,evidence,**kwargs):
        stored=db_session.get(Conversation,uuid.UUID(conversation['id']))
        stored.active_execution_id=uuid.uuid4() # Another execution has claimed the same idempotent request.
        db_session.commit()
        return AnswerDraft(supported=True,answer='Late old result',confidence=.9,citation_ids=[evidence[0]['id']],missing_information=[])
    monkeypatch.setattr(deepseek,'answer_question',abandoned)
    result=client.post(path,json=dict(request_id=str(uuid.uuid4()),question='Which database?',retrieval_mode='vector'))
    assert result.status_code==409 and result.json()['error']['code']=='TURN_REPLACED'
    assert client.get(path).json()['items'][0]['answer'] is None


def test_failed_turn_requires_explicit_retry_and_live_lease_blocks_double_send(client, db_session, configured, monkeypatch):
    from datetime import timedelta
    from app.core.errors import AppError
    from app.models.domain import utc_now
    from app.models.workspace import Conversation
    project,settings=prepared_project(client,monkeypatch)
    monkeypatch.setattr(routes,'get_settings',lambda:settings)
    base=f'/api/v1/projects/{project}/conversations'
    conversation=client.post(base,json={}).json();path=base+f"/{conversation['id']}/turns"
    request=dict(request_id=str(uuid.uuid4()),question='Which database?',retrieval_mode='vector')
    def fail(*_a,**_kw):
        raise AppError(status_code=503,code='PROVIDER_TEST_FAILURE',message='Synthetic failure')
    monkeypatch.setattr(deepseek,'answer_question',fail)
    assert client.post(path,json=request).status_code==503
    assert client.get(path).json()['items'][0]['status']=='failed'
    assert client.post(path,json=request).json()['error']['code']=='TURN_RETRY_REQUIRED'
    monkeypatch.setattr(deepseek,'answer_question',lambda _s,_q,evidence,**_kw:AnswerDraft(
        supported=True,answer='PostgreSQL',confidence=.9,citation_ids=[evidence[0]['id']],missing_information=[]))
    assert client.post(path,json={**request,'retry_interrupted':True}).status_code==200
    stored=db_session.get(Conversation,uuid.UUID(conversation['id']))
    stored.active_request_id=uuid.uuid4();stored.lease_until=utc_now()+timedelta(minutes=5);db_session.commit()
    response=client.post(path,json={**request,'request_id':str(uuid.uuid4())})
    assert response.status_code==409 and response.json()['error']['code']=='CONVERSATION_BUSY'
