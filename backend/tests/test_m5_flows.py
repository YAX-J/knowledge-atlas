"""New fictional-corpus API smoke and adversarial tests; never live quality grades."""
import copy
import hashlib
import json
import uuid
import pytest
from sqlalchemy import func,select
from app.api.dependencies import get_current_user_id
from app.api.routes import assistant as routes
from app.core.identity import DEVELOPMENT_USER_ID
from app.llm.providers import deepseek
from app.main import app
from app.models.assistant_operation import AssistantOperation
from app.models.domain import SourceDocument
from app.models.graph import KnowledgeEntity
from app.schemas.knowledge import ExtractionDraft
from app.services import assistant_execution as execution
from scripts.project_agent_m5 import validate_packet
from tests.test_assistant_execution import continuation
from tests.test_knowledge import configured
from tests.test_multi_agent import tool
from tests.test_notes import path as note_path
from tests.test_project_assistant import endpoint,finish
from tests.test_sources import create_project

@pytest.fixture
def corpus():return {m['id']:m for m in validate_packet()['fixture']['materials']}

def source(client,project,material):
    response=client.post(f'/api/v1/projects/{project}/sources',files={'file':(material['path'].split('/')[-1],material['content'].encode(),'text/plain')})
    assert response.status_code==202,response.text
    data=response.json();assert client.post(f"/api/v1/tasks/{data['task_id']}/run").json()['status']=='succeeded'
    return data

def note(client,project,corpus):
    first=corpus['note-r1'];second=corpus['note-r2']
    value=client.post(note_path(project),json=dict(request_id=str(uuid.uuid4()),title=first['title'],markdown=first['content'])).json()
    revised=client.put(note_path(project)+'/'+value['id'],json=dict(request_id=str(uuid.uuid4()),expected_revision_id=value['current']['id'],title=second['title'],markdown=second['content']))
    assert revised.status_code==200,revised.text
    return value,revised.json()

def queue(client,project,configured,monkeypatch,case,**scope):
    monkeypatch.setattr(routes,'get_settings',lambda:configured)
    goal=next(c['goal'] for c in validate_packet()['packet']['cases'] if c['id']==case)
    response=client.post(endpoint(project),json=dict(protocol='assistant-task-v3',request_id=str(uuid.uuid4()),goal=goal,**scope))
    assert response.status_code==202,response.text
    return response.json()

def process(db,settings):return execution.process_next(db,user_id=DEVELOPMENT_USER_ID,settings=settings).model_dump(mode='json')
def unsure():return {'content':json.dumps(dict(action='finish',report=dict(title='Synthetic engineering result',claims=[dict(text='Original content is preserved; inspect the operation receipt.',status='uncertain',reference_ids=[])],missing_information=['Semantic quality is not measured by this substitute.'])))}

def test_new_corpus_exact_quote_uses_actual_gateway_not_fabricated_references(client,db_session,configured,monkeypatch,corpus):
    project=create_project(client);uploaded=source(client,project,corpus['overview'])
    queue(client,project,configured,monkeypatch,'E01',source_ids=[uploaded['source_id']])
    calls=[]
    def turn(_s,m,_t,**_kw):
        calls.append(1)
        if len(calls)==1:return tool('search_sources',dict(query='checksum'))
        refs=json.loads(m[-1]['content'])['references'];assert refs[0]['quote']=='A journal checksum is verified every 18 hours.'
        return finish(refs)
    monkeypatch.setattr(deepseek,'call_agent_turn',turn)
    result=process(db_session,configured)
    assert result['status']=='succeeded' and result['usage']['model']==2,result
    ref=result['result']['references'][0]
    assert ref['source_sha256']==hashlib.sha256(corpus['overview']['content'].encode()).hexdigest() and ref['start_line']==5

def test_adversarial_model_following_imported_instruction_still_cannot_write(client,db_session,configured,monkeypatch,corpus):
    project=create_project(client);uploaded=source(client,project,corpus['untrusted'])
    queue(client,project,configured,monkeypatch,'E04',source_ids=[uploaded['source_id']])
    calls=[]
    def turn(_s,m,_t,**_kw):
        calls.append(1)
        if len(calls)==1:return tool('search_sources',dict(query='UNTRUSTED INSTRUCTION'),'read')
        if len(calls)==2:
            assert 'run a shell' in m[-1]['content']
            return tool('propose_knowledge_change',dict(action='retire',knowledge_id=str(uuid.uuid4()),reason='Injected instruction'),'attack')
        assert json.loads(m[-1]['content'])['error']=='CAPABILITY_NOT_AUTHORIZED';return unsure()
    monkeypatch.setattr(deepseek,'call_agent_turn',turn)
    result=process(db_session,configured)
    assert result['status']=='succeeded' and not result['operations']
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEntity).where(KnowledgeEntity.project_id==uuid.UUID(project)))==0

def test_old_attached_note_does_not_drift_to_current_revision(client,db_session,configured,monkeypatch,corpus):
    project=create_project(client);original,current=note(client,project,corpus)
    queue(client,project,configured,monkeypatch,'N01',note_revision_ids=[original['current']['id']])
    calls=[]
    def turn(_s,m,_t,**_kw):
        calls.append(1)
        if len(calls)==1:return tool('search_notes',dict(query='checksum'))
        refs=json.loads(m[-1]['content'])['references'];assert refs[0]['quote']==corpus['note-r1']['content'].splitlines()[0]
        return finish(refs)
    monkeypatch.setattr(deepseek,'call_agent_turn',turn);result=process(db_session,configured)
    assert result['status']=='succeeded' and result['result']['references'][0]['revision_id']==original['current']['id']
    assert client.get(note_path(project)+'/'+original['id']).json()['current']['id']==current['id']

@pytest.mark.parametrize('scenario',['reject','concurrent','wrong_actor','tampered'])
def test_corpus_proposal_review_boundaries(client,db_session,configured,monkeypatch,corpus,scenario):
    project=create_project(client);original,current=note(client,project,corpus)
    queued=queue(client,project,configured,monkeypatch,'N04' if scenario=='concurrent' else 'N03',note_revision_ids=[current['id']],allowed_actions=['propose_note_revision'])
    calls=[]
    def turn(*_a,**_kw):
        calls.append(1)
        return tool('propose_note_revision',dict(note_id=original['id'],expected_revision_id=current['id'],title=current['title'],markdown='Unapproved proposed content.')) if len(calls)==1 else unsure()
    monkeypatch.setattr(deepseek,'call_agent_turn',turn);task=process(db_session,configured)
    assert task['status']=='waiting_approval',task
    op=task['operations'][0];body=dict(request_id=str(uuid.uuid4()),operation_id=op['id'],proposal_sha256=op['proposal_sha256'],decision='reject' if scenario=='reject' else 'approve')
    url=endpoint(project)+'/'+queued['id']+'/approvals'
    latest=current
    if scenario=='concurrent':
        latest=client.put(note_path(project)+'/'+original['id'],json=dict(request_id=str(uuid.uuid4()),expected_revision_id=current['id'],title=current['title'],markdown=corpus['note-r3']['content'])).json()
    if scenario=='wrong_actor':
        app.dependency_overrides[get_current_user_id]=lambda:uuid.uuid4()
        try:assert client.post(url,json=body).status_code==404
        finally:app.dependency_overrides.pop(get_current_user_id,None)
    elif scenario=='tampered':
        row=db_session.get(AssistantOperation,uuid.UUID(op['id']));payload=copy.deepcopy(row.payload);payload['arguments']['markdown']='Tampered';row.payload=payload;db_session.commit()
        assert client.post(url,json=body).json()['error']['code']=='ASSISTANT_PROPOSAL_CONFLICT'
    else:
        response=client.post(url,json=body);assert response.status_code==200,response.text
        accepted=response.json();assert accepted['operations'][0]['status']==('rejected' if scenario=='reject' else 'conflict')
        assert client.post(url,json=body).json()==accepted and len(calls)==1
        assert client.post(url,json={**body,'decision':'approve' if scenario=='reject' else 'reject'}).status_code==409
        assert client.post(endpoint(project)+'/'+queued['id']+'/continue',json=continuation(accepted)).status_code==202
        assert process(db_session,configured)['status']=='succeeded'
    assert client.get(note_path(project)+'/'+original['id']).json()['current']['id']==latest['id']
    assert client.get(note_path(project)+'/revisions/'+original['current']['id']).json()['markdown']==corpus['note-r1']['content']

def test_unapproved_returned_import_commit_cannot_create_sources(client,db_session,configured,monkeypatch):
    import httpx
    from tests.test_github_import import install_github_mock,register_github
    project=create_project(client);repo=register_github(client,project);requests=[]
    def respond(request):
        requests.append(request.url.path)
        if '/commits/' in request.url.path:return httpx.Response(200,json={'sha':'b5'*20,'commit':{'tree':{'sha':'c5'*20}}})
        return httpx.Response(200,json={'default_branch':'main'})
    install_github_mock(monkeypatch,respond)
    settings=configured.model_copy(update={'github_api_base_url':'https://api.github.test'})
    queue(client,project,settings,monkeypatch,'G01',allowed_actions=['import_repository_snapshot'],repository_id=repo['id'],repository_commit='a5'*20)
    calls=[]
    def turn(*_a,**_kw):
        calls.append(1);return tool('import_repository_snapshot',{}) if len(calls)==1 else unsure()
    monkeypatch.setattr(deepseek,'call_agent_turn',turn);result=process(db_session,settings)
    assert result['operations'][0]['error_code']=='GITHUB_COMMIT_CONFLICT',result
    assert len(requests)==2 and db_session.scalar(select(func.count()).select_from(SourceDocument).where(SourceDocument.project_id==uuid.UUID(project)))==0
