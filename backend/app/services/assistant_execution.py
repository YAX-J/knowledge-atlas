"""Explicit async-v2 queue and fenced execution. Reads never recover or execute tasks."""
from datetime import datetime, timedelta
import hashlib
import json
import time
import uuid

from sqlalchemy import func, or_, select, update

from app.agents.registry import get_agent
from app.agents.runtime import RunContext, run_scope
from app.core.errors import AppError
from app.llm.providers.deepseek import CallAgentError
from app.models.assistant_task import AssistantTask, AssistantAttempt, AssistantStep, AssistantArtifact, AssistantContinuation
from app.models.domain import Project, utc_now
from app.models.graph import KnowledgeEvidence
from app.schemas.assistant import AssistantRead, AssistantReference, AssistantResult, ReportClaim, ReportDraft, AssistantRequest
from app.services import project_assistant as tasks
from app.services.projects import get_project
from app.tools.project import ProjectTools

LEASE_SECONDS = 300


def _fail(code, message, status=409):
    raise AppError(status_code=status,code=code,message=message)


def _filters(model, item):
    return (model.task_id==item.id,model.user_id==item.user_id,model.project_id==item.project_id)


def _last(db,item):
    return db.scalar(select(AssistantStep).where(*_filters(AssistantStep,item)).order_by(AssistantStep.sequence.desc()).limit(1))


def _attempts(db,item):
    return list(db.scalars(select(AssistantAttempt).where(*_filters(AssistantAttempt,item))))


def _remaining(item,last,attempts=()):
    preparation = item.request['scope'].get('repository_progress')
    if preparation and preparation['phase'] != 'reporting':
        return not preparation.get('blocked')
    if last and last.state['loop'].get('next_node')=='done':return True
    coordinator={kind:sum(a.agent=='project_assistant' and a.kind==kind for a in attempts) for kind in ('model','tool')}
    role_limits=(8,16) if item.execution_mode=='async_v3' else (4,8)
    return (item.elapsed_ms<230000 and item.usage.get('model',0)<item.request['model_limit'] and coordinator['model']<role_limits[0]
        and (not last or last.state['loop'].get('next_node')!='tools'
             or item.usage.get('tool',0)<item.request['tool_limit'] and coordinator['tool']<role_limits[1]))


def read_execution(db,item):
    last=_last(db,item)
    attempts=_attempts(db,item)
    from app.services.assistant_operations import operations, public
    ops=operations(db,item)
    pending=any(o.status=='pending' for o in ops)
    return dict(checkpoint_id=last.id if last else None,
        unknown_model_attempts=sum(a.kind=='model' and a.status in {'started','unknown'} for a in attempts),
        can_continue=tasks._status(item) in {'interrupted','failed','waiting_approval'} and not pending and _remaining(item,last,attempts),
        operations=[public(o) for o in ops],unknown_operations=sum(o.status in {'executing','unknown'} for o in ops),
        final_artifact_id=uuid.uuid5(item.id,'assistant-report-v1') if item.status=='succeeded' and item.result else None,
        remaining={k:max(0,min(item.request[k+'_limit']-item.usage.get(k,0),limit-sum(a.agent=='project_assistant' and a.kind==k for a in attempts))) for k,limit in ([('model',8),('tool',16)] if item.execution_mode=='async_v3' else [('model',4),('tool',8)])},
        artifact_ids=list(db.scalars(select(AssistantArtifact.id).where(*_filters(AssistantArtifact,item)))))


def _contract(settings,workflow=False):
    from app.agents.project_assistant.agent import PROMPT_VERSION
    from app.tools.workspace import WorkspaceTools
    return dict(version='assistant-loop-v3' if workflow else 'assistant-loop-v2',prompt='project-assistant-v3' if workflow else PROMPT_VERSION,model=settings.deepseek_model,
        endpoint_sha256=hashlib.sha256(settings.deepseek_base_url.rstrip('/').encode()).hexdigest(),
        tools_sha256=hashlib.sha256(json.dumps(WorkspaceTools.definitions if workflow else ProjectTools.definitions,sort_keys=True).encode()).hexdigest())


def enqueue(db,*,user_id,project_id,request,settings):
    get_project(db,user_id=user_id,project_id=project_id)
    data=request.request_data()
    digest=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    db.execute(select(Project.id).where(Project.id==project_id,Project.user_id==user_id).with_for_update())
    existing=db.get(AssistantTask,request.request_id)
    if existing:
        if existing.user_id!=user_id or existing.project_id!=project_id:
            _fail('ASSISTANT_NOT_FOUND','任务不属于当前范围',404)
        if existing.input_sha256!=digest:_fail('ASSISTANT_REQUEST_CONFLICT','任务标识已绑定其他输入')
        db.commit()
        return tasks.read_task(db,user_id=user_id,project_id=project_id,task_id=existing.id)
    sources,paths,commit=tasks._freeze_sources(db,user_id=user_id,project_id=project_id,request=request)
    scope=dict(source_ids=[str(s.id) for s in sources],source_versions=[dict(id=str(s.id),sha256=s.content_sha256) for s in sources],
        snapshot_id=str(request.snapshot_id) if request.snapshot_id else None,commit_sha=commit,
        valid_at=data['valid_at'],knowledge_at=data['valid_at'] or utc_now().isoformat(),retrieval_mode='bm25',
        runtime_contract=_contract(settings,request.protocol=='assistant-task-v3'),
        capabilities=list(ProjectTools.contracts),embedding_limit=0,
        limits=dict(model=request.model_limit,tool=request.tool_limit,seconds=230,coordinator_model=4,coordinator_tool=8,
            source_bytes=200000,chunks=500,references=32))
    workflow=request.protocol=='assistant-task-v3'
    if workflow:
        from app.services import notes
        from app.tools.workspace import WorkspaceTools
        revisions=[notes.revision(db,user_id=user_id,project_id=project_id,revision_id=i) for i in request.note_revision_ids]
        if sum(len(r.markdown)+len(r.title) for r in revisions)>200000:_fail('ASSISTANT_SCOPE_TOO_LARGE','笔记范围超过 200000 字符',422)
        scope.update(note_versions=[dict(id=str(r.id),note_id=str(r.note_id),sha256=r.content_sha256) for r in revisions],
            allowed_actions=request.allowed_actions,capabilities=list(WorkspaceTools.contracts))
        scope['limits'].update(coordinator_model=8,coordinator_tool=16)
        if request.repository_id:
            from app.services.repositories import get_repository
            repo=get_repository(db,user_id=user_id,project_id=project_id,repository_id=request.repository_id)
            scope['repository_identity']=[repo.provider,repo.remote_owner,repo.remote_name]
            if request.whole_repository:
                if repo.provider != 'github':
                    _fail('GITHUB_REPOSITORY_REQUIRED','请选择已登记的 GitHub 仓库')
                scope['repository_progress'] = dict(phase='importing', snapshot_id=None, commit_sha=None,
                                                    completed_files=0, total_files=0, pending_directories=0)
                scope['repository_provider_id'] = repo.provider_repository_id
    runtime=RunContext(user_id=user_id,project_id=project_id,model_limit=request.model_limit,
        tool_limit=request.tool_limit,embedding_limit=0)
    db.add(AssistantTask(id=request.request_id,user_id=user_id,project_id=project_id,status='queued',
        execution_mode='async_v3' if workflow else 'async_v2',input_sha256=digest,request={**data,'scope':scope},events=[],usage=runtime.usage()))
    db.commit()
    return tasks.read_task(db,user_id=user_id,project_id=project_id,task_id=request.request_id)


def _locked(db,*,user_id,project_id,task_id):
    get_project(db,user_id=user_id,project_id=project_id)
    item=db.scalar(select(AssistantTask).where(AssistantTask.id==task_id,AssistantTask.user_id==user_id,
        AssistantTask.project_id==project_id).with_for_update().execution_options(populate_existing=True))
    if item is None:_fail('ASSISTANT_NOT_FOUND','助手任务不属于当前范围',404)
    if item.execution_mode not in {'async_v2','async_v3'}:_fail('ASSISTANT_LEGACY_TASK','旧同步任务不支持队列控制')
    return item


def _event(item,kind,status):
    if len(item.events)>=250:_fail('AGENT_BUDGET_EXCEEDED','事件预算已用尽',429)
    item.events=[*item.events,dict(sequence=len(item.events)+1,agent='project_assistant',kind=kind,
        status=status,elapsed_ms=item.elapsed_ms)]


def _unknown(db,item):
    for attempt in _attempts(db,item):
        if attempt.status=='started':attempt.status='unknown'
    from app.services.assistant_operations import operations
    for op in operations(db,item):
        if op.status=='executing':op.status='unknown'


def cancel(db,*,user_id,project_id,task_id):
    item=_locked(db,user_id=user_id,project_id=project_id,task_id=task_id)
    if item.status not in {'succeeded','cancelled'}:
        _unknown(db,item)
        _event(item,'cancel','succeeded')
        item.status='cancelled';item.execution_id=None;item.lease_until=None;item.revision+=1
    db.commit()
    return tasks.read_task(db,user_id=user_id,project_id=project_id,task_id=task_id)


def continue_task(db,*,user_id,project_id,task_id,request):
    item=_locked(db,user_id=user_id,project_id=project_id,task_id=task_id)
    digest=hashlib.sha256(request.model_dump_json().encode()).hexdigest()
    previous=db.get(AssistantContinuation,request.request_id)
    if previous:
        if (previous.task_id,previous.user_id,previous.project_id)!=(task_id,user_id,project_id):
            _fail('ASSISTANT_NOT_FOUND','继续请求不属于当前范围',404)
        if previous.input_sha256!=digest:_fail('ASSISTANT_REQUEST_CONFLICT','继续标识已绑定其他输入')
        db.commit()
        return tasks.read_task(db,user_id=user_id,project_id=project_id,task_id=task_id)
    last=_last(db,item)
    if item.revision!=request.expected_revision or (last.id if last else None)!=request.checkpoint_id:
        _fail('ASSISTANT_CHECKPOINT_CONFLICT','检查点或执行版本已变化，请刷新')
    from app.services.assistant_operations import operations
    ops=operations(db,item)
    if tasks._status(item) not in {'interrupted','failed','waiting_approval'} or any(o.status=='pending' for o in ops):_fail('ASSISTANT_NOT_CONTINUABLE','任务尚不能继续')
    if not _remaining(item,last,_attempts(db,item)):_fail('AGENT_BUDGET_EXCEEDED','累计任务预算已用尽',429)
    if (any(a.kind=='model' and a.status in {'started','unknown'} for a in _attempts(db,item)) or any(o.status in {'executing','unknown'} for o in ops)) and not request.acknowledge_unknown:
        _fail('ASSISTANT_UNKNOWN_ACK_REQUIRED','需明确确认未知调用仍保留计数，继续可能发起新的付费尝试')
    _unknown(db,item)
    _event(item,'continue','saved')
    item.status='queued';item.execution_id=None;item.lease_until=None;item.error_code=None;item.revision+=1
    db.add(AssistantContinuation(id=request.request_id,task_id=task_id,user_id=user_id,project_id=project_id,input_sha256=digest))
    db.commit()
    return tasks.read_task(db,user_id=user_id,project_id=project_id,task_id=task_id)


def recover_expired(db,*,user_id):
    items=list(db.scalars(select(AssistantTask).where(AssistantTask.user_id==user_id,
        AssistantTask.execution_mode.in_(['async_v2','async_v3']),AssistantTask.status=='running',
        or_(AssistantTask.lease_until.is_(None),AssistantTask.lease_until<=utc_now()))
        .order_by(AssistantTask.created_at).limit(20).with_for_update(skip_locked=True).execution_options(populate_existing=True)))
    for item in items:
        _unknown(db,item);_event(item,'interruption','saved')
        item.status='interrupted';item.execution_id=None;item.lease_until=None;item.revision+=1
    db.commit()
    return len(items)


def claim_next(db,*,user_id):
    recover_expired(db,user_id=user_id)
    item=db.scalar(select(AssistantTask).join(Project,Project.id==AssistantTask.project_id).where(
        AssistantTask.user_id==user_id,Project.user_id==user_id,Project.archived_at.is_(None),
        AssistantTask.execution_mode.in_(['async_v2','async_v3']),AssistantTask.status=='queued',
        or_(AssistantTask.lease_until.is_(None), AssistantTask.lease_until<=utc_now()))
        .order_by(AssistantTask.created_at,AssistantTask.id).limit(1).with_for_update(skip_locked=True,of=AssistantTask)
        .execution_options(populate_existing=True))
    if item is None:db.rollback();return None
    item.execution_id=uuid.uuid4();item.lease_until=utc_now()+timedelta(seconds=LEASE_SECONDS)
    item.status='running';item.revision+=1
    if not item.request['scope'].get('repository_progress') or not any(event['kind']=='claim' for event in item.events):
        _event(item,'claim','started')
    db.commit()
    return item.id,item.execution_id


def _save(db,item,execution,runtime,*,commit=True):
    if db.new or db.dirty or db.deleted:_fail('WORKFLOW_PROGRESS_UNAVAILABLE','拒绝顺带提交业务写入',503)
    now=utc_now()
    changed=db.execute(update(AssistantTask).where(AssistantTask.id==item.id,AssistantTask.user_id==item.user_id,
        AssistantTask.project_id==item.project_id,AssistantTask.execution_id==execution,AssistantTask.status=='running',
        AssistantTask.lease_until>now,AssistantTask.project_id.in_(select(Project.id).where(Project.user_id==item.user_id,
            Project.archived_at.is_(None)))).values(events=list(runtime.events),usage=runtime.usage(),
                elapsed_ms=int((time.monotonic()-runtime.started)*1000),lease_until=now+timedelta(seconds=LEASE_SECONDS))
        .execution_options(synchronize_session=False))
    if changed.rowcount!=1:db.rollback();_fail('ASSISTANT_INTERRUPTED','执行归属已失效')
    if commit:db.commit()


def execute_claim(db,*,task_id,execution,settings,user_id):
    item=db.scalar(select(AssistantTask).where(AssistantTask.id==task_id,AssistantTask.user_id==user_id,
        AssistantTask.execution_mode.in_(['async_v2','async_v3']),AssistantTask.execution_id==execution,AssistantTask.status=='running')
        .execution_options(populate_existing=True))
    if item is None:_fail('ASSISTANT_INTERRUPTED','任务执行归属已失效')
    request=AssistantRequest.model_validate({k:v for k,v in item.request.items() if k!='scope'}|{'request_id':item.id})
    attempts=_attempts(db,item)
    counts={kind:item.usage.get(kind,0) for kind in ('model','tool','embedding')}
    runtime=RunContext(user_id=item.user_id,project_id=item.project_id,run_id=item.id,model_limit=request.model_limit,
        tool_limit=request.tool_limit,embedding_limit=0,seconds=230,events=list(item.events),counts=counts,
        started=time.monotonic()-item.elapsed_ms/1000)
    if item.execution_mode=='async_v3':
        runtime.role_limits={'project_assistant':{'model':8,'tool':16}}
    for a in attempts:runtime.agent_counts[a.agent+':'+a.kind]=runtime.agent_counts.get(a.agent+':'+a.kind,0)+1
    def progress(context):
        _save(db,item,execution,context,commit=False)
        event=context.events[-1]
        if event['kind'] in {'model','tool'} and event['status']=='started':
            db.add(AssistantAttempt(task_id=item.id,user_id=item.user_id,project_id=item.project_id,kind=event['kind'],
                agent=event['agent'],ordinal=event['attempt'],status='started'))
        db.commit()
    runtime.on_progress=progress
    from app.services.assistant_operations import AwaitingApproval, operations
    workflow=item.execution_mode=='async_v3'
    result=None;error_code=None;waiting=False
    try:
        with run_scope(runtime):
            if item.request['scope']['runtime_contract']!=_contract(settings,workflow):
                _fail('ASSISTANT_RUNTIME_CHANGED','运行契约或模型配置已变化，请核对后新建任务')
            repository_context = None
            if request.whole_repository:
                from app.services import assistant_repository
                from app.services.assistant_operations import guard
                try:
                    repository_context = assistant_repository.prepare(db,item,execution,request,settings,LEASE_SECONDS)
                finally:
                    # Deterministic import/parse time is separate from the model budget.
                    runtime.started = time.monotonic() - item.elapsed_ms / 1000
                if repository_context is None:
                    guard(db,item,execution,lock=True)
                    item.status = 'queued'
                    item.execution_id = None
                    phase = item.request['scope']['repository_progress']['phase']
                    item.lease_until = utc_now() + timedelta(seconds=2) if phase == 'parsing' else None
                    db.commit()
                    return tasks.read_task(db,user_id=item.user_id,project_id=item.project_id,task_id=item.id)
            runtime.event('assistant','started')
            sources,paths,commit=tasks._freeze_sources(db,user_id=item.user_id,project_id=item.project_id,request=request)
            if [dict(id=str(s.id),sha256=s.content_sha256) for s in sources]!=item.request['scope']['source_versions']:
                _fail('ASSISTANT_SOURCE_CHANGED','所选来源版本已变化')
            gateway=tasks.make_gateway(db,user_id=item.user_id,project_id=item.project_id,request=request,settings=settings,
                sources=sources,paths=paths,commit=commit,knowledge_at=datetime.fromisoformat(item.request['scope']['knowledge_at']))
            if workflow:
                from app.tools.workspace import WorkspaceTools
                gateway=WorkspaceTools(gateway,db=db,item=item,execution=execution,settings=settings,request=request,
                                       repository_context=repository_context)
                versions=[dict(id=str(r.id),note_id=str(r.note_id),sha256=r.content_sha256) for r in gateway.notes.values()]
                if versions!=item.request['scope']['note_versions']:_fail('ASSISTANT_NOTE_CHANGED','笔记修订版本已变化')
            last=_last(db,item)
            resume=last.state['loop'] if last else None
            if last:
                gateway.references={ref.id:ref for ref in [AssistantReference.model_validate(v) for v in last.state['references']]}
            def checkpoint(kind,state):
                data=dict(loop=state,references=[v.model_dump(mode='json') for v in gateway.references.values()])
                if len(json.dumps(data,ensure_ascii=False))>200000:_fail('ASSISTANT_CHECKPOINT_TOO_LARGE','检查点过大')
                _save(db,item,execution,runtime,commit=False)
                previous=_last(db,item)
                sequence=(previous.sequence if previous else 0)+1
                if sequence>(40 if workflow else 16):_fail('AGENT_BUDGET_EXCEEDED','检查点预算已用尽',429)
                for a in _attempts(db,item):
                    if a.kind==kind and a.agent=='project_assistant' and a.status=='started':a.status='succeeded'
                db.add(AssistantStep(task_id=item.id,user_id=item.user_id,project_id=item.project_id,sequence=sequence,kind=kind,state=data))
                db.commit()
                runtime.event('step_checkpoint','saved')
                if any(o.status=='pending' for o in operations(db,item)):raise AwaitingApproval()
            if workflow and resume:
                # Approval is read-only here; add the exact saved outcome once per operation.
                seen=set(resume.get('operation_outcomes',[]))
                outcomes=[o for o in operations(db,item) if o.status in {'approved','rejected','conflict'} and str(o.id) not in seen]
                if outcomes:
                    resume={**resume,'messages':[*resume['messages'],dict(role='user',content=json.dumps(dict(
                        server_operation_outcomes=[dict(id=str(o.id),status=o.status,result=o.result,error_code=o.error_code,
                            references=gateway.approved_references(o) if o.status=='approved' else []) for o in outcomes])))],
                        'operation_outcomes':[*seen,*[str(o.id) for o in outcomes]]}
                    checkpoint('input',resume)
            has_knowledge=db.scalar(select(KnowledgeEvidence.id).where(KnowledgeEvidence.user_id==item.user_id,
                KnowledgeEvidence.project_id==item.project_id).limit(1))
            if request.whole_repository and not gateway.sources and not request.note_revision_ids:
                result = AssistantResult(protocol='assistant-report-v2',action='finish',report=ReportDraft(title='仓库材料不足',
                    claims=[ReportClaim(text='固定快照中没有符合报告读取范围的已解析文件。',status='uncertain',reference_ids=[])],
                    missing_information=['请核对快照中的跳过和解析失败记录。']))
            elif not sources and not has_knowledge and not (workflow and (request.note_revision_ids or request.allowed_actions)):
                result=AssistantResult(action='finish',report=ReportDraft(title='缺少项目材料',claims=[ReportClaim(
                    text='当前范围没有可读取的资料或已确认知识证据。',status='uncertain',reference_ids=[])],missing_information=['请选择已解析资料或审核项目知识。']))
            else:
                result=get_agent('project_assistant').run(request,dict(settings=settings,tools=gateway,scope=item.request['scope'],
                    resume_state=resume,on_checkpoint=checkpoint,seconds=max(.01,230-item.elapsed_ms/1000)))
            runtime.event('report_checkpoint','saved')
    except AwaitingApproval:
        db.rollback();waiting=True
    except (AppError,CallAgentError) as exc:
        db.rollback();error_code=exc.code
    except Exception:
        db.rollback();error_code='ASSISTANT_FAILED'
    # Reacquire the same fence before finalizing either an error or the artifact.
    try:
        _save(db,item,execution,runtime,commit=False)
    except AppError:
        db.rollback()
        return tasks.read_task(db,user_id=item.user_id,project_id=item.project_id,task_id=item.id)
    _unknown(db,item)
    values=dict(status='waiting_approval' if waiting else 'failed' if error_code else 'succeeded',error_code=error_code,execution_id=None,lease_until=None,
        result=result.model_dump(mode='json') if result else None,revision=AssistantTask.revision+1)
    db.execute(update(AssistantTask).where(AssistantTask.id==item.id,AssistantTask.execution_id==execution).values(**values)
        .execution_options(synchronize_session=False))
    if result and not error_code:
        db.add(AssistantArtifact(id=uuid.uuid5(item.id,'assistant-report-v1'),task_id=item.id,user_id=item.user_id,
            project_id=item.project_id,result=result.model_dump(mode='json')))
    db.commit()
    return tasks.read_task(db,user_id=item.user_id,project_id=item.project_id,task_id=item.id)


def process_next(db,*,user_id,settings):
    claimed=claim_next(db,user_id=user_id)
    if claimed is None:return None
    return execute_claim(db,task_id=claimed[0],execution=claimed[1],settings=settings,user_id=user_id)


def read_artifact(db,*,user_id,project_id,task_id,artifact_id):
    tasks.read_task(db,user_id=user_id,project_id=project_id,task_id=task_id)
    item=db.scalar(select(AssistantArtifact).where(AssistantArtifact.id==artifact_id,AssistantArtifact.task_id==task_id,
        AssistantArtifact.user_id==user_id,AssistantArtifact.project_id==project_id))
    if item is None:_fail('ASSISTANT_ARTIFACT_NOT_FOUND','产物不属于当前任务',404)
    return AssistantResult.model_validate(item.result)
