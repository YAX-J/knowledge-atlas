"""M3/M4 workflow acceptance with local substitutes, zero external requests."""
import json
import uuid
import pytest
from sqlalchemy import func, select
from app.core.identity import DEVELOPMENT_USER_ID
from app.models.domain import CandidateKnowledge, SourceDocument
from app.models.graph import KnowledgeEntity
from app.models.notes import NoteRevision, Note
from app.models.assistant_operation import AssistantOperation
from app.llm.providers import deepseek
from app.services import assistant_execution as execution
from app.api.routes import assistant as routes
from tests.test_knowledge import configured, parsed_source
from tests.test_sources import create_project
from tests.test_notes import create, path as notes_path
from tests.test_project_assistant import endpoint, request, finish, setup_source
from tests.test_assistant_execution import continuation
from tests.test_multi_agent import tool

def queue(client,project,**kwargs):
    body=request(protocol='assistant-task-v3',**kwargs)
    response=client.post(endpoint(project),json=body)
    assert response.status_code==202,response.text
    return response.json()
def process(db,settings):return execution.process_next(db,user_id=DEVELOPMENT_USER_ID,settings=settings).model_dump(mode='json')
def uncertain():return {'content':json.dumps(dict(action='finish',report=dict(title='处理记录',claims=[dict(text='需要人工核对。',status='uncertain',reference_ids=[])],missing_information=['请核对原文。'])))}
def approve(client,project,task,**changes):
    op=task['operations'][-1]
    body=dict(request_id=str(uuid.uuid4()),operation_id=op['id'],proposal_sha256=op['proposal_sha256'],decision='approve')|changes
    response=client.post(endpoint(project)+'/'+task['id']+'/approvals',json=body)
    return response,body

def test_note_reference_is_pinned_and_report_saved_editable(client,db_session,configured,monkeypatch):
    project=create_project(client);note=create(client,project);revision=note['current']
    monkeypatch.setattr(routes,'get_settings',lambda:configured)
    queued=queue(client,project,note_revision_ids=[revision['id']])
    calls=[]
    def turn(_s,m,_t,**_kw):
        calls.append(1)
        if len(calls)==1:return tool('search_notes',{'query':'PostgreSQL'})
        return finish(json.loads(m[-1]['content'])['references'])
    monkeypatch.setattr(deepseek,'call_agent_turn',turn)
    task=process(db_session,configured)
    assert task['status']=='succeeded',task
    assert task['result']['protocol']=='assistant-report-v2'
    ref=task['result']['references'][0]
    assert ref['kind']=='note' and ref['revision_id']==revision['id'] and ref['source_id'] is None
    edit=client.put(notes_path(project)+'/'+note['id'],json=dict(request_id=str(uuid.uuid4()),expected_revision_id=revision['id'],title='changed',markdown='changed'))
    assert edit.status_code==200
    assert client.get(endpoint(project)+'/'+queued['id']).json()['result']==task['result']
    url=endpoint(project)+'/'+task['id']+'/artifacts/'+task['artifact_ids'][0]+'/note'
    body={'request_id':str(uuid.uuid4())};saved=client.post(url,json=body)
    assert saved.status_code==200,saved.text
    assert saved.json()['current']['origin']=='assistant' and saved.json()['current']['provenance']['report']==task['result']
    assert client.post(url,json=body).json()==saved.json()
    assert len(calls)==2

@pytest.mark.parametrize('decision',['approve','reject','conflict'])
def test_note_proposal_pauses_bound_approval_then_explicit_continue(client,db_session,configured,monkeypatch,decision):
    project=create_project(client);note=create(client,project);rev=note['current']
    monkeypatch.setattr(routes,'get_settings',lambda:configured)
    queue(client,project,note_revision_ids=[rev['id']],allowed_actions=['propose_note_revision'])
    calls=[]
    def turn(_s,m,_t,**_kw):
        calls.append(1)
        if len(calls)==1:return tool('propose_note_revision',dict(note_id=note['id'],expected_revision_id=rev['id'],title='Agent 修订',markdown='New proposed content'))
        assert 'server_operation_outcomes' in m[-1]['content']
        return uncertain()
    monkeypatch.setattr(deepseek,'call_agent_turn',turn)
    task=process(db_session,configured)
    assert task['status']=='waiting_approval' and len(calls)==1,task
    assert task['events'][-1]['status']=='waiting_approval'
    assert not task['can_continue']
    bad,_=approve(client,project,task,proposal_sha256='0'*64)
    assert bad.status_code==409
    if decision=='conflict':
        assert client.put(notes_path(project)+'/'+note['id'],json=dict(request_id=str(uuid.uuid4()),expected_revision_id=rev['id'],title='Human',markdown='Human edit')).status_code==200
    response,body=approve(client,project,task,decision='reject' if decision=='reject' else 'approve')
    assert response.status_code==200,response.text
    accepted=response.json();assert accepted['operations'][-1]['status']=={'approve':'approved','reject':'rejected','conflict':'conflict'}[decision]
    assert accepted['status']=='waiting_approval' and accepted['can_continue'] and len(calls)==1
    assert client.post(endpoint(project)+'/'+task['id']+'/approvals',json=body).json()==accepted
    assert client.post(endpoint(project)+'/'+task['id']+'/continue',json=continuation(accepted)).status_code==202
    done=process(db_session,configured)
    assert done['status']=='succeeded' and len(calls)==2,done
    latest=client.get(notes_path(project)+'/'+note['id']).json()['current']
    assert latest['markdown']==('New proposed content' if decision=='approve' else 'Human edit' if decision=='conflict' else rev['markdown'])
    assert client.get(notes_path(project)+'/revisions/'+rev['id']).json()==rev

def test_capability_refusal_and_draft_idempotency(client,db_session,configured,monkeypatch):
    project=create_project(client);monkeypatch.setattr(routes,'get_settings',lambda:configured)
    queue(client,project,allowed_actions=['create_note_draft'])
    def turn(_s,m,_t,**_kw):
        if m[-1]['role']=='user':return tool('create_note_draft',dict(title='New draft',markdown='Unconfirmed content.'))
        return uncertain()
    monkeypatch.setattr(deepseek,'call_agent_turn',turn)
    task=process(db_session,configured)
    assert task['status']=='succeeded',task
    assert task['operations'][0]['status']=='succeeded'
    assert db_session.scalar(select(func.count()).select_from(Note))==1
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEntity).where(KnowledgeEntity.project_id==uuid.UUID(project)))==0

def test_parse_extract_human_confirm_pipeline_shares_budget(client,db_session,configured,monkeypatch):
    project,source,draft=parsed_source(client)
    monkeypatch.setattr(routes,'get_settings',lambda:configured)
    queue(client,project,source_ids=[source['source_id']],allowed_actions=['request_source_parse','propose_knowledge','propose_knowledge_change'])
    # Existing deterministic fixture extraction model returns evidence-bound candidates.
    calls=[]
    def turn(_s,m,_t,**_kw):
        calls.append(1)
        if len(calls)==1:return tool('request_source_parse',{'source_id':source['source_id']},'parse')
        if len(calls)==2:return tool('propose_knowledge',{'source_id':source['source_id']},'extract')
        if len(calls)==3:
            result=json.loads(m[-1]['content'])['operation']['result']
            ids=[c['id'] for c in result['candidates'] if c['kind']=='entity']
            assert ids
            return tool('propose_knowledge_change',dict(action='confirm_candidates',reason='原文证据一致',candidate_ids=ids),'confirm')
        return uncertain()
    monkeypatch.setattr(deepseek,'call_agent_turn',turn)
    from app.schemas.knowledge import ExtractionDraft
    monkeypatch.setattr(deepseek,'extract_candidates',lambda *_a,**_k:ExtractionDraft.model_validate(draft))
    task=process(db_session,configured)
    assert task['status']=='waiting_approval',task
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEntity).where(KnowledgeEntity.project_id==uuid.UUID(project)))==0
    response,_=approve(client,project,task)
    assert response.status_code==200,response.text
    assert response.json()['operations'][-1]['status']=='approved',response.json()
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEntity).where(KnowledgeEntity.project_id==uuid.UUID(project)))>0
    accepted=response.json()
    assert client.post(endpoint(project)+'/'+task['id']+'/continue',json=continuation(accepted)).status_code==202
    assert process(db_session,configured)['status']=='succeeded'

@pytest.mark.parametrize('action',['merge','supersede','retire'])
def test_formal_governance_only_applies_after_exact_human_approval(client,db_session,configured,monkeypatch,action):
    from tests.test_evolution import pair, proposal
    project,old,new=pair(client,monkeypatch)
    monkeypatch.setattr(routes,'get_settings',lambda:configured)
    args=dict(action=action,reason='人工核对后确认')
    if action=='supersede':args['change']=proposal(old,new)
    else:
        args['knowledge_id']=old['entity']['id']
        if action=='merge':args['target_id']=new['entity']['id']
    queue(client,project,allowed_actions=['propose_knowledge_change'])
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_k:tool('propose_knowledge_change',args))
    task=process(db_session,configured)
    assert task['status']=='waiting_approval',task
    assert client.get('/api/v1/knowledge/entities/'+old['entity']['id']).status_code==200
    response,body=approve(client,project,task)
    assert response.status_code==200,response.text
    op=response.json()['operations'][-1]
    assert op['status']=='approved',op
    assert op['result']
    assert client.post(endpoint(project)+'/'+task['id']+'/approvals',json=body).json()==response.json()
    if action=='supersede':assert op['result']['new_entity_id']==new['entity']['id'] and op['result']['old_entity_id']==old['entity']['id']

def test_import_pins_commit_then_scopes_parse_to_its_receipt(client,db_session,configured,monkeypatch):
    import httpx
    from tests.test_github_import import register_github, install_github_mock
    project=create_project(client);repo=register_github(client,project);http=[]
    def respond(req):
        http.append(req.url.path)
        if req.url.path=='/repos/example/demo':return httpx.Response(200,json={'default_branch':'main'})
        if '/commits/' in req.url.path:
            assert req.url.path.endswith('a'*40)
            return httpx.Response(200,json={'sha':'a'*40,'commit':{'tree':{'sha':'t'*40}}})
        if '/git/trees/' in req.url.path:return httpx.Response(200,json={'truncated':False,'tree':[{'path':'README.md','type':'blob','sha':'blob','size':18}]})
        return httpx.Response(200,content=b'# Import\n\nEvidence from a fixed commit.\n')
    install_github_mock(monkeypatch,respond)
    settings=configured.model_copy(update={'github_api_base_url':'https://api.github.test'})
    monkeypatch.setattr(routes,'get_settings',lambda:settings)
    queue(client,project,allowed_actions=['import_repository_snapshot','request_source_parse','propose_knowledge','propose_knowledge_change'],repository_id=repo['id'],repository_commit='a'*40)
    calls=[]
    def turn(_s,m,_t,**_kw):
        calls.append(1)
        if len(calls)==1:return tool('import_repository_snapshot',{},'import')
        if len(calls)==2:
            receipt=json.loads(m[-1]['content'])['operation']['result']
            return tool('request_source_parse',{'source_id':receipt['items'][0]['source_id']},'parse')
        if len(calls)==3:
            return tool('propose_knowledge',{'source_id':json.loads(m[-1]['content'])['operation']['result']['source_id']},'extract')
        if len(calls)==4:
            candidates=json.loads(m[-1]['content'])['operation']['result']['candidates']
            return tool('propose_knowledge_change',dict(action='confirm_candidates',reason='Reviewed import evidence',candidate_ids=[c['id'] for c in candidates]),'confirm')
        outcomes=json.loads(m[-1]['content'])['server_operation_outcomes']
        return finish(outcomes[0]['references'])
    monkeypatch.setattr(deepseek,'call_agent_turn',turn)
    from app.schemas.knowledge import ExtractionDraft
    def extract(_settings,chunks):
        return ExtractionDraft.model_validate(dict(entities=[dict(local_id='fact',type='Concept',name='Fixed import',summary='Pinned evidence',confidence=.8,
            evidence=[dict(chunk_id=chunks[-1]['chunk_id'],quote=chunks[-1]['content'])])],relations=[]))
    monkeypatch.setattr(deepseek,'extract_candidates',extract)
    task=process(db_session,settings)
    assert task['status']=='waiting_approval',task
    assert [o['status'] for o in task['operations']]==['succeeded','succeeded','succeeded','pending']
    response,_=approve(client,project,task)
    assert response.json()['operations'][-1]['status']=='approved',response.json()
    assert client.post(endpoint(project)+'/'+task['id']+'/continue',json=continuation(response.json())).status_code==202
    task=process(db_session,settings)
    assert task['status']=='succeeded' and task['usage']['model']==6,task
    assert task['result']['references'][0]['kind']=='knowledge'
    assert len(http)==4
    source=db_session.scalar(select(SourceDocument).where(SourceDocument.project_id==uuid.UUID(project)))
    assert source.status.value=='ready'
    before=len(http)
    assert client.get(endpoint(project)+'/'+task['id']).status_code==200
    assert execution.process_next(db_session,user_id=DEVELOPMENT_USER_ID,settings=settings) is None
    assert len(http)==before

def test_capability_and_note_scope_rejected_without_side_effects(client,db_session,configured,monkeypatch):
    project=create_project(client);note=create(client,project)
    monkeypatch.setattr(routes,'get_settings',lambda:configured)
    queue(client,project,note_revision_ids=[note['current']['id']])
    calls=[]
    def turn(_s,m,_t,**_kw):
        calls.append(1)
        if len(calls)==1:return tool('create_note_draft',{'title':'unauthorized','markdown':'blocked'})
        assert json.loads(m[-1]['content'])['error']=='CAPABILITY_NOT_AUTHORIZED'
        return uncertain()
    monkeypatch.setattr(deepseek,'call_agent_turn',turn)
    task=process(db_session,configured)
    assert task['status']=='succeeded'
    assert not task['operations'] and db_session.scalar(select(func.count()).select_from(Note))==1

def test_cancelled_proposal_cannot_be_approved(client,db_session,configured,monkeypatch):
    project=create_project(client);note=create(client,project)
    monkeypatch.setattr(routes,'get_settings',lambda:configured)
    queue(client,project,note_revision_ids=[note['current']['id']],allowed_actions=['propose_note_revision'])
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_kw:tool('propose_note_revision',dict(note_id=note['id'],expected_revision_id=note['current']['id'],title='Changed',markdown='Changed')))
    task=process(db_session,configured)
    assert task['status']=='waiting_approval',task
    assert client.post(endpoint(project)+'/'+task['id']+'/cancel').json()['status']=='cancelled'
    response,_=approve(client,project,task)
    assert response.status_code==409
    assert db_session.scalar(select(func.count()).select_from(NoteRevision))==1

def test_nested_extraction_cancel_cannot_publish_candidates(client,db_session,configured,monkeypatch):
    from app.schemas.knowledge import ExtractionDraft
    project,source,draft=parsed_source(client);monkeypatch.setattr(routes,'get_settings',lambda:configured)
    task=queue(client,project,source_ids=[source['source_id']],allowed_actions=['propose_knowledge'])
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_kw:tool('propose_knowledge',{'source_id':source['source_id']}))
    def extract(*_a,**_kw):
        execution.cancel(db_session,user_id=DEVELOPMENT_USER_ID,project_id=uuid.UUID(project),task_id=uuid.UUID(task['id']))
        return ExtractionDraft.model_validate(draft)
    monkeypatch.setattr(deepseek,'extract_candidates',extract)
    task=process(db_session,configured)
    assert task['status']=='cancelled',task
    assert db_session.scalar(select(func.count()).select_from(CandidateKnowledge).where(CandidateKnowledge.project_id==uuid.UUID(project)))==0

def test_unknown_local_operation_reconciles_without_duplicate_draft(client,db_session,configured,monkeypatch):
    from tests.test_assistant_execution import Crash, expire
    from app.services import assistant_operations
    project=create_project(client);monkeypatch.setattr(routes,'get_settings',lambda:configured)
    task=queue(client,project,allowed_actions=['create_note_draft'])
    calls=[]
    def turn(_s,m,_t,**_kw):
        calls.append(1)
        return tool('create_note_draft',{'title':'draft','markdown':'one'},'stable') if len(calls)==1 else uncertain()
    monkeypatch.setattr(deepseek,'call_agent_turn',turn)
    original=assistant_operations.execute
    def crash(*a,**kw):
        original(*a,**kw);raise Crash()
    monkeypatch.setattr(assistant_operations,'execute',crash)
    with pytest.raises(Crash):process(db_session,configured)
    expire(db_session,task['id'])
    execution.recover_expired(db_session,user_id=DEVELOPMENT_USER_ID)
    current=client.get(endpoint(project)+'/'+task['id']).json()
    assert db_session.scalar(select(func.count()).select_from(Note))==1
    monkeypatch.setattr(assistant_operations,'execute',original)
    assert client.post(endpoint(project)+'/'+task['id']+'/continue',json=continuation(current)).status_code==202
    result=process(db_session,configured)
    assert result['status']=='succeeded',result
    assert db_session.scalar(select(func.count()).select_from(Note))==1

def test_native_cancel_in_another_transaction_rejects_late_note_write(db_session,configured,monkeypatch):
    import os
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import delete
    from sqlalchemy.orm import Session
    from app.models.domain import Project
    from app.schemas.assistant import AssistantRequest
    from app.tools.workspace import WorkspaceTools
    if not os.environ.get('KA_ACCEPTANCE_SCHEMA'):pytest.skip('PostgreSQL transaction fencing acceptance')
    engine=db_session.get_bind().engine;project_id=uuid.uuid4();entered=threading.Event();release=threading.Event()
    with Session(engine,expire_on_commit=False) as db:
        db.add(Project(id=project_id,user_id=DEVELOPMENT_USER_ID,name='Disposable M4 cancel race'));db.commit()
        job=execution.enqueue(db,user_id=DEVELOPMENT_USER_ID,project_id=project_id,settings=configured,
            request=AssistantRequest(request_id=uuid.uuid4(),protocol='assistant-task-v3',goal='Draft',allowed_actions=['create_note_draft']))
        claimed=execution.claim_next(db,user_id=DEVELOPMENT_USER_ID)
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_kw:tool('create_note_draft',{'title':'Must rollback','markdown':'Late content'}))
    original=WorkspaceTools._perform
    def paused(self,*a,**kw):entered.set();assert release.wait(10);return original(self,*a,**kw)
    monkeypatch.setattr(WorkspaceTools,'_perform',paused)
    def run():
        with Session(engine,expire_on_commit=False) as db:return execution.execute_claim(db,task_id=job.id,execution=claimed[1],settings=configured,user_id=DEVELOPMENT_USER_ID)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(run)
            assert entered.wait(10)
            with Session(engine,expire_on_commit=False) as db:
                assert execution.cancel(db,user_id=DEVELOPMENT_USER_ID,project_id=project_id,task_id=job.id).status=='cancelled'
            release.set();assert future.result(timeout=15).status=='cancelled'
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(Note).where(Note.project_id==project_id))==0
            assert db.scalar(select(AssistantOperation.status).where(AssistantOperation.task_id==job.id))=='unknown'
    finally:
        release.set()
        with Session(engine) as db:db.execute(delete(Project).where(Project.id==project_id));db.commit()

def test_note_snapshot_parse_independent_report_artifact_and_edited_provenance(client,db_session,configured,monkeypatch):
    project=create_project(client);note=create(client,project);monkeypatch.setattr(routes,'get_settings',lambda:configured)
    queue(client,project,note_revision_ids=[note['current']['id']],allowed_actions=['request_source_parse','create_report_draft'])
    calls=[]
    def turn(_s,m,_t,**_kw):
        calls.append(1)
        if len(calls)==1:return tool('snapshot_note_revision',dict(revision_id=note['current']['id']),'snapshot')
        if len(calls)==2:return tool('request_source_parse',dict(source_id=json.loads(m[-1]['content'])['operation']['result']['source_id']),'parse')
        if len(calls)==3:return tool('search_sources',dict(query='PostgreSQL'),'search')
        refs=[r for msg in m if msg['role']=='tool' for r in json.loads(msg['content']).get('references',[])]
        if len(calls)==4:return tool('create_report_draft',dict(report=json.loads(finish(refs)['content'])['report']),'report')
        return finish(refs)
    monkeypatch.setattr(deepseek,'call_agent_turn',turn)
    task=process(db_session,configured)
    assert task['status']=='succeeded',task
    assert len(task['artifact_ids'])==2 and task['final_artifact_id'] in task['artifact_ids']
    artifact=next(o for o in task['operations'] if o['kind']=='create_report_draft')['result']['artifact_id']
    saved=client.post(endpoint(project)+'/'+task['id']+'/artifacts/'+artifact+'/note',json={'request_id':str(uuid.uuid4())}).json()
    current=saved['current'];body=dict(request_id=str(uuid.uuid4()),expected_revision_id=current['id'],title=current['title'],markdown='Human rewrite')
    url=notes_path(project)+'/'+saved['id'];edited=client.put(url,json=body)
    assert edited.status_code==200,edited.text
    assert edited.json()['provenance']==current['provenance']
    assert client.put(url,json=body).json()==edited.json()

def test_identity_change_invalidates_formal_proposal_even_when_original_entity_is_unchanged(client,db_session,configured,monkeypatch):
    from tests.test_evolution import pair
    project,old,new=pair(client,monkeypatch);monkeypatch.setattr(routes,'get_settings',lambda:configured)
    queue(client,project,allowed_actions=['propose_knowledge_change'])
    args=dict(action='merge',knowledge_id=old['entity']['id'],target_id=new['entity']['id'],reason='Reviewed identity')
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_kw:tool('propose_knowledge_change',args))
    task=process(db_session,configured);assert task['status']=='waiting_approval',task
    response=client.post(f'/api/v1/projects/{project}/knowledge-operations',json=dict(request_id=str(uuid.uuid4()),
        action='alias',knowledge_id=old['entity']['id'],alias='A new human alias',reason='Human identity update'))
    assert response.status_code==200,response.text
    response,_=approve(client,project,task)
    op=response.json()['operations'][-1]
    assert op['status']=='conflict' and op['error_code']=='ASSISTANT_TARGET_CHANGED',op

def test_completed_code_specialist_counts_once_and_is_not_reported_unknown(client,db_session,configured,monkeypatch):
    from app.agents.runtime import agent_scope, invoke_model
    from tests.test_code_agent import _code, _repository
    project=create_project(client);repository=_repository(client,project)
    source=_code(client,project,repository,'main.py','def run():\n    return 1\n')
    monkeypatch.setattr(routes,'get_settings',lambda:configured)
    queue(client,project,source_ids=[source['source_id']])
    def analyze(*_a,**_kw):
        with agent_scope('code_analysis'):return invoke_model(lambda:dict(findings=[],syntax_only=True))
    monkeypatch.setattr('app.services.agent_workflows.analyze_code',analyze)
    calls=[]
    def turn(*_a,**_kw):
        calls.append(1)
        return tool('analyze_code',dict(source_id=source['source_id'])) if len(calls)==1 else uncertain()
    monkeypatch.setattr(deepseek,'call_agent_turn',turn)
    task=process(db_session,configured)
    assert task['status']=='succeeded' and task['usage']['model']==3 and task['unknown_model_attempts']==0,task

def test_large_note_proposal_reaches_approval_without_repeating_full_before_content_into_model(client,db_session,configured,monkeypatch):
    project=create_project(client);monkeypatch.setattr(routes,'get_settings',lambda:configured)
    note=client.post(notes_path(project),json=dict(request_id=str(uuid.uuid4()),title='Long note',markdown='a'*45000)).json()
    queue(client,project,note_revision_ids=[note['current']['id']],allowed_actions=['propose_note_revision'])
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_kw:tool('propose_note_revision',dict(note_id=note['id'],expected_revision_id=note['current']['id'],title='Updated long note',markdown='b'*45000)))
    task=process(db_session,configured)
    assert task['status']=='waiting_approval',task
    assert len(task['operations'][0]['payload']['before']['markdown'])==45000
    response,_=approve(client,project,task)
    assert response.json()['operations'][0]['status']=='approved',response.json()
