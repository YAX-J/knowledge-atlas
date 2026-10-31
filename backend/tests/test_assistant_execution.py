"""Deterministic queue/crash/cancel/continuation acceptance with zero provider traffic."""
from datetime import timedelta
import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.agents.runtime import RunContext
from app.core.errors import AppError
from app.core.identity import DEVELOPMENT_USER_ID
from app.models.assistant_task import AssistantTask, AssistantAttempt, AssistantStep, AssistantArtifact
from app.models.domain import Project, utc_now
from app.llm.providers import deepseek
from app.services import assistant_execution as execution
from app import assistant_runner
from app.schemas.assistant import AssistantRequest
from app.tools.project import ProjectTools
from tests.test_knowledge import configured
from tests.test_project_assistant import endpoint, request, setup_source, finish
from tests.test_multi_agent import tool


class Crash(BaseException):
    pass


def queue(client,configured,monkeypatch,**kwargs):
    project,source=setup_source(client,configured,monkeypatch)
    body=request([source['source_id']],**kwargs)
    body['protocol']='assistant-task-v2'
    response=client.post(endpoint(project),json=body)
    assert response.status_code==202,response.text
    return project,body,response.json()


def steady(_settings,messages,_tools,**_kwargs):
    if messages[-1]['role']=='user':return tool('search_sources',{'query':'PostgreSQL'})
    references=[ref for msg in messages if msg['role']=='tool' for ref in json.loads(msg['content']).get('references',[])]
    return finish(list({r['id']:r for r in references}.values()))


def process(db,settings):
    return execution.process_next(db,user_id=DEVELOPMENT_USER_ID,settings=settings)


def expire(db,id):
    item=db.scalar(select(AssistantTask).where(AssistantTask.id==uuid.UUID(id)).execution_options(populate_existing=True))
    item.lease_until=utc_now()-timedelta(seconds=1);db.commit()


def continuation(task,**kwargs):
    return dict(request_id=str(uuid.uuid4()),expected_revision=task['revision'],checkpoint_id=task['checkpoint_id'],**kwargs)


def test_queued_submit_get_replay_events_and_artifact_are_free(client,db_session,configured,monkeypatch):
    operation=client.get('/openapi.json').json()['paths']['/api/v1/projects/{project_id}/assistant/tasks']['post']
    assert {'200','202'}.issubset(operation['responses'])
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_k:pytest.fail('Submission must never execute'))
    project,body,data=queue(client,configured,monkeypatch)
    path=endpoint(project)
    assert data['status']=='queued' and data['usage']['model']==0
    assert client.post(path,json=body).json()==data
    assert client.get(path+'/'+data['id']).json()==data
    assert client.get(path+'/'+data['id']+'/events').json()==dict(items=[],next_sequence=0,has_more=False)
    assert client.post(path,json={**body,'model_limit':1}).status_code==409
    monkeypatch.setattr(deepseek,'call_agent_turn',steady)
    result=process(db_session,configured)
    assert result.status=='succeeded',result
    assert result.usage['model']==2 and result.usage['tool']==1 and result.usage['embedding']==0
    attempts=list(db_session.scalars(select(AssistantAttempt)))
    assert len(attempts)==3 and all(a.status=='succeeded' for a in attempts)
    assert len(result.artifact_ids)==1
    assert client.get(path+'/'+data['id']+'/artifacts/'+str(result.artifact_ids[0])).json()==result.result.model_dump(mode='json')
    page=client.get(path+'/'+data['id']+'/events?limit=2').json()
    assert len(page['items'])==2 and page['has_more']
    assert all(e['sequence']>page['next_sequence'] for e in client.get(path+'/'+data['id']+'/events',params={'after':page['next_sequence']}).json()['items'])
    assert 'PostgreSQL' not in json.dumps([e.model_dump() for e in result.events])
    assert client.post(path,json=body).json()['status']=='succeeded'
    assert process(db_session,configured) is None


def test_unknown_transport_requires_explicit_ack_and_never_automatically_replays(client,db_session,configured,monkeypatch):
    project,body,_=queue(client,configured,monkeypatch)
    seen=[]
    def crashing(*args,**kwargs):
        seen.append(1)
        # Reservation is visible durably before transport starts.
        assert db_session.scalar(select(AssistantAttempt.status).where(AssistantAttempt.kind=='model',AssistantAttempt.ordinal==len(seen)))=='started'
        if len(seen)==2:raise Crash()
        return steady(*args,**kwargs)
    monkeypatch.setattr(deepseek,'call_agent_turn',crashing)
    with pytest.raises(Crash):process(db_session,configured)
    expire(db_session,body['request_id'])
    path=endpoint(project)+'/'+body['request_id']
    read=client.get(path).json()
    assert read['status']=='interrupted' and read['unknown_model_attempts']==1
    assert len(seen)==2
    assert process(db_session,configured) is None
    read=client.get(path).json()
    assert client.post(path+'/continue',json=continuation(read)).json()['error']['code']=='ASSISTANT_UNKNOWN_ACK_REQUIRED'
    control=continuation(read,acknowledge_unknown=True)
    assert client.post(path+'/continue',json=control).status_code==202
    assert client.post(path+'/continue',json=control).json()['status']=='queued'
    done=process(db_session,configured)
    assert done.status=='succeeded' and done.usage['model']==3 and done.usage['tool']==1
    assert len(seen)==3
    assert client.post(path+'/continue',json=control).json()['status']=='succeeded'
    assert process(db_session,configured) is None
    assert client.post(path+'/continue',json={**control,'acknowledge_unknown':False}).status_code==409


@pytest.mark.parametrize('checkpoint_number',[1,2,3])
def test_continuation_reuses_each_saved_model_or_tool_and_can_finish_at_budget(client,db_session,configured,monkeypatch,checkpoint_number):
    project,body,_=queue(client,configured,monkeypatch,model_limit=2)
    seen=[];tools=[]
    original_event=RunContext.event;original_tool=ProjectTools.execute
    checkpoints=[]
    def event(self,kind,*args,**kwargs):
        if kind=='step_checkpoint':
            checkpoints.append(kind)
            if len(checkpoints)==checkpoint_number:raise Crash()
        return original_event(self,kind,*args,**kwargs)
    def tracked_tool(self,name,args):
        tools.append(name);return original_tool(self,name,args)
    def provider(*args,**kwargs):seen.append(1);return steady(*args,**kwargs)
    monkeypatch.setattr(RunContext,'event',event)
    monkeypatch.setattr(ProjectTools,'execute',tracked_tool)
    monkeypatch.setattr(deepseek,'call_agent_turn',provider)
    with pytest.raises(Crash):process(db_session,configured)
    monkeypatch.setattr(RunContext,'event',original_event)
    expire(db_session,body['request_id'])
    assert process(db_session,configured) is None
    path=endpoint(project)+'/'+body['request_id']
    current=client.get(path).json()
    assert current['can_continue'] and current['unknown_model_attempts']==0
    assert client.post(path+'/continue',json=continuation(current)).status_code==202
    done=process(db_session,configured)
    assert done.status=='succeeded',done
    assert len(seen)==2 and tools==['search_sources']
    assert done.usage['model']==2 and done.usage['tool']==1


def test_cancel_during_transport_fences_all_later_writes_and_preserves_charge(client,db_session,configured,monkeypatch):
    project,body,_=queue(client,configured,monkeypatch)
    path=endpoint(project)+'/'+body['request_id']
    seen=[]
    def provider(*_a,**_kw):
        seen.append(1)
        assert client.post(path+'/cancel').json()['status']=='cancelled'
        return {'content':json.dumps(dict(action='ask_user',question='Late answer must not publish'))}
    monkeypatch.setattr(deepseek,'call_agent_turn',provider)
    result=process(db_session,configured)
    assert result.status=='cancelled' and result.result is None
    assert result.usage['model']==1 and result.unknown_model_attempts==1 and len(seen)==1
    assert db_session.scalar(select(func.count()).select_from(AssistantArtifact))==0
    before=client.get(path).json()
    assert client.post(path+'/cancel').json()==before
    assert client.post(path+'/continue',json=continuation(before,acknowledge_unknown=True)).status_code==409


def test_queued_cancel_budget_exhaustion_and_project_scope(client,db_session,configured,monkeypatch):
    project,body,data=queue(client,configured,monkeypatch,model_limit=0)
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_kw:pytest.fail('Budget zero'))
    failed=process(db_session,configured)
    assert failed.status=='failed' and failed.error_code=='AGENT_BUDGET_EXCEEDED' and not failed.can_continue
    path=endpoint(project)+'/'+body['request_id']
    assert client.post(path+'/continue',json=continuation(client.get(path).json())).status_code==429
    other=client.post('/api/v1/projects',json={'name':'Other'}).json()['id']
    for suffix in ('/cancel','/continue'):
        assert client.post(endpoint(other)+'/'+data['id']+suffix,json=continuation(data)).status_code==404
    assert client.get(endpoint(other)+'/'+data['id']+'/events').status_code==404
    assert client.get(path+'/artifacts/'+str(uuid.uuid4())).status_code==404
    new={**body,'request_id':str(uuid.uuid4()),'model_limit':8}
    queued=client.post(endpoint(project),json=new).json()
    assert client.post(endpoint(project)+'/'+queued['id']+'/cancel').json()['status']=='cancelled'
    assert process(db_session,configured) is None


def test_stale_revision_checkpoint_and_legacy_tasks_are_refused(client,db_session,configured,monkeypatch):
    project,body,_=queue(client,configured,monkeypatch)
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_k:(_ for _ in ()).throw(Crash()))
    with pytest.raises(Crash):process(db_session,configured)
    expire(db_session,body['request_id']);execution.recover_expired(db_session,user_id=DEVELOPMENT_USER_ID)
    path=endpoint(project)+'/'+body['request_id'];current=client.get(path).json()
    assert client.post(path+'/continue',json={**continuation(current),'expected_revision':0}).status_code==409
    assert client.post(path+'/continue',json={**continuation(current),'checkpoint_id':str(uuid.uuid4())}).status_code==409
    record=db_session.get(AssistantTask,uuid.UUID(body['request_id']));record.execution_mode='sync_v1';db_session.commit()
    assert client.post(path+'/cancel').json()['error']['code']=='ASSISTANT_LEGACY_TASK'
    assert process(db_session,configured) is None


def test_progress_failure_prevents_transport(client,db_session,configured,monkeypatch):
    queue(client,configured,monkeypatch)
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_k:pytest.fail('No reservation, no provider'))
    original=execution._save
    def unavailable(db,item,execution_id,runtime,**kwargs):
        if runtime.events[-1]['kind']=='model':
            raise AppError(status_code=503,code='WORKFLOW_PROGRESS_UNAVAILABLE',message='Unavailable')
        return original(db,item,execution_id,runtime,**kwargs)
    monkeypatch.setattr(execution,'_save',unavailable)
    result=process(db_session,configured)
    assert result.status=='failed' and result.error_code=='WORKFLOW_PROGRESS_UNAVAILABLE'


def test_native_single_claim_among_two_consumers(db_session,configured):
    if not os.environ.get('KA_ACCEPTANCE_SCHEMA'):pytest.skip('Native scoped row locking requires PostgreSQL')
    engine=db_session.get_bind().engine
    project_id=uuid.uuid4()
    with Session(engine,expire_on_commit=False) as db:
        db.add(Project(id=project_id,user_id=DEVELOPMENT_USER_ID,name='Disposable claim race'));db.commit()
        job=execution.enqueue(db,user_id=DEVELOPMENT_USER_ID,project_id=project_id,
            request=AssistantRequest(request_id=uuid.uuid4(),protocol='assistant-task-v2',goal='No provider'),settings=configured)
    barrier=threading.Barrier(2)
    def claim():
        with Session(engine,expire_on_commit=False) as db:
            barrier.wait(timeout=5)
            return execution.claim_next(db,user_id=DEVELOPMENT_USER_ID)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:claim(),range(2)))
        assert sum(r is not None for r in results)==1
        assert next(r for r in results if r)[0]==job.id
    finally:
        with Session(engine) as db:db.execute(delete(Project).where(Project.id==project_id));db.commit()


def test_mid_tool_batch_resumes_only_unsaved_calls(client,db_session,configured,monkeypatch):
    project,body,_=queue(client,configured,monkeypatch)
    original=RunContext.event;count=[];seen=[];tools=[]
    execute=ProjectTools.execute
    def record(self,name,args):tools.append(name);return execute(self,name,args)
    def provider(_settings,messages,_tools,**kwargs):
        seen.append(1)
        if messages[-1]['role']=='user':
            return dict(tool_calls=tool('search_sources',{'query':'PostgreSQL'},'one')['tool_calls']+
                tool('search_sources',{'query':'Decision'},'two')['tool_calls'])
        return steady(_settings,messages,_tools,**kwargs)
    def crash(self,kind,*args,**kwargs):
        if kind=='step_checkpoint':
            count.append(1)
            if len(count)==2:raise Crash()
        return original(self,kind,*args,**kwargs)
    monkeypatch.setattr(deepseek,'call_agent_turn',provider);monkeypatch.setattr(ProjectTools,'execute',record)
    monkeypatch.setattr(RunContext,'event',crash)
    with pytest.raises(Crash):process(db_session,configured)
    monkeypatch.setattr(RunContext,'event',original)
    expire(db_session,body['request_id']);execution.recover_expired(db_session,user_id=DEVELOPMENT_USER_ID)
    path=endpoint(project)+'/'+body['request_id'];current=client.get(path).json()
    assert client.post(path+'/continue',json=continuation(current)).status_code==202
    result=process(db_session,configured)
    assert result.status=='succeeded' and tools==['search_sources','search_sources'] and len(seen)==2
    assert result.usage['tool']==2


@pytest.mark.parametrize('limit',[1,8])
def test_unknown_attempts_never_reset_task_or_role_budget(client,db_session,configured,monkeypatch,limit):
    project,body,_=queue(client,configured,monkeypatch,model_limit=limit)
    seen=[]
    def crash(*_a,**_k):seen.append(1);raise Crash()
    monkeypatch.setattr(deepseek,'call_agent_turn',crash)
    path=endpoint(project)+'/'+body['request_id']
    for number in range(min(4,limit)):
        with pytest.raises(Crash):process(db_session,configured)
        expire(db_session,body['request_id']);execution.recover_expired(db_session,user_id=DEVELOPMENT_USER_ID)
        read=client.get(path).json()
        assert read['usage']['model']==number+1 and read['unknown_model_attempts']==number+1
        response=client.post(path+'/continue',json=continuation(read,acknowledge_unknown=True))
        assert response.status_code==(202 if number+1<min(4,limit) else 429)
    assert len(seen)==min(4,limit) and process(db_session,configured) is None


def test_runtime_version_drift_and_source_drift_stop_before_provider(client,db_session,configured,monkeypatch):
    from app.models.domain import SourceDocument
    _,body,_=queue(client,configured,monkeypatch)
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_k:pytest.fail('Changed version must be free'))
    changed=configured.model_copy(update={'deepseek_model':'new-model'})
    result=process(db_session,changed)
    assert result.error_code=='ASSISTANT_RUNTIME_CHANGED' and result.usage['model']==0
    project,body,_=queue(client,configured,monkeypatch)
    source=db_session.get(SourceDocument,uuid.UUID(body['source_ids'][0]));source.content_sha256='f'*64;db_session.commit()
    result=process(db_session,configured)
    assert result.error_code=='ASSISTANT_SOURCE_CHANGED' and result.usage['model']==0


def test_old_execution_cannot_publish_after_expiry_and_explicit_reclaim(client,db_session,configured,monkeypatch):
    project,body,_=queue(client,configured,monkeypatch)
    first=execution.claim_next(db_session,user_id=DEVELOPMENT_USER_ID)
    expire(db_session,body['request_id']);execution.recover_expired(db_session,user_id=DEVELOPMENT_USER_ID)
    path=endpoint(project)+'/'+body['request_id'];value=client.get(path).json()
    assert client.post(path+'/continue',json=continuation(value)).status_code==202
    second=execution.claim_next(db_session,user_id=DEVELOPMENT_USER_ID)
    assert first[1]!=second[1]
    with pytest.raises(AppError):execution.execute_claim(db_session,task_id=first[0],execution=first[1],settings=configured,user_id=DEVELOPMENT_USER_ID)
    monkeypatch.setattr(deepseek,'call_agent_turn',steady)
    result=execution.execute_claim(db_session,task_id=second[0],execution=second[1],settings=configured,user_id=DEVELOPMENT_USER_ID)
    assert result.status=='succeeded'


def test_runner_once_stopping_and_safe_errors(client,db_session,configured,monkeypatch,caplog):
    from contextlib import nullcontext
    queue(client,configured,monkeypatch)
    monkeypatch.setattr(deepseek,'call_agent_turn',steady)
    assert assistant_runner.serve(settings=configured,stop=threading.Event(),once=True,session_factory=lambda:nullcontext(db_session))==0
    stop=threading.Event();stop.set()
    assert assistant_runner.serve(settings=configured,stop=stop,session_factory=lambda:pytest.fail('Stopped runner must be idle'))==0
    def fail(*_a,**_k):raise ValueError('private request content')
    monkeypatch.setattr(assistant_runner,'process_next',fail)
    assert assistant_runner.serve(settings=configured,stop=threading.Event(),once=True,session_factory=lambda:nullcontext(db_session))==1
    assert 'private request content' not in caplog.text


def test_archival_prevents_claim_and_progress_refuses_pending_writes(client,db_session,configured,monkeypatch):
    project,body,_=queue(client,configured,monkeypatch)
    item=db_session.get(Project,uuid.UUID(project));item.archived_at=utc_now();db_session.commit()
    assert process(db_session,configured) is None
    item.archived_at=None;db_session.commit()
    def provider(*_a,**_k):
        db_session.add(Project(user_id=DEVELOPMENT_USER_ID,name='Must not flush'))
        return {'content':json.dumps(dict(action='ask_user',question='Test pending writes'))}
    monkeypatch.setattr(deepseek,'call_agent_turn',provider)
    result=process(db_session,configured)
    assert result.error_code=='WORKFLOW_PROGRESS_UNAVAILABLE'
    assert db_session.scalar(select(func.count()).select_from(Project).where(Project.name=='Must not flush'))==0
