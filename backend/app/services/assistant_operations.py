"""Version-bound proposals and exactly-once human decisions over existing services."""
from contextlib import contextmanager
import hashlib
import json
import uuid
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session
from app.core.errors import AppError
from app.models.assistant_task import AssistantTask, AssistantArtifact, AssistantAttempt
from app.models.assistant_operation import AssistantOperation, AssistantApproval
from app.models.domain import CandidateKnowledge, Project, utc_now
from app.models.graph import KnowledgeEntity, KnowledgeRelationship, KnowledgeEvidence
from app.models.workspace import EntityAlias, EntityMerge, KnowledgePeriod
from app.models.evolution import KnowledgeChange
from app.schemas.assistant_operations import ChangeArgs
from app.schemas.notes import NoteCreate, NoteEdit
from app.services import notes
from app.agents.runtime import AgentPaused


class AwaitingApproval(AgentPaused):pass
VERSION_MODELS={'candidate':CandidateKnowledge,'entity':KnowledgeEntity,'relationship':KnowledgeRelationship,
    'evidence':KnowledgeEvidence,'alias':EntityAlias,'merge':EntityMerge,'period':KnowledgePeriod,'change':KnowledgeChange}

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
def fail(code,message,status=409):raise AppError(status_code=status,code=code,message=message)

def public(op):
    return dict(id=str(op.id),kind=op.kind,status=op.status,proposal_sha256=op.proposal_sha256,
        payload=op.payload,result=op.result,error_code=op.error_code)

def operations(db,item):
    return list(db.scalars(select(AssistantOperation).where(AssistantOperation.task_id==item.id,
        AssistantOperation.user_id==item.user_id,AssistantOperation.project_id==item.project_id)
        .order_by(AssistantOperation.created_at,AssistantOperation.id).limit(32)))

def guard(db,item,execution,*,lock=False):
    with db.no_autoflush:
        query=select(AssistantTask.id).join(Project,Project.id==AssistantTask.project_id).where(
            AssistantTask.id==item.id,AssistantTask.user_id==item.user_id,AssistantTask.project_id==item.project_id,
            AssistantTask.execution_id==execution,AssistantTask.status=='running',AssistantTask.lease_until>utc_now(),
            Project.user_id==item.user_id,Project.archived_at.is_(None))
        if lock:
            db.execute(select(Project.id).where(Project.id==item.project_id,Project.user_id==item.user_id).with_for_update())
            query=query.with_for_update(of=AssistantTask)
        if db.scalar(query) is None:fail('ASSISTANT_INTERRUPTED','任务已取消或执行归属已失效')

@contextmanager
def fenced(db,item,execution):
    def before_commit(session):guard(session,item,execution,lock=True)
    event.listen(db,'before_commit',before_commit)
    try:yield
    finally:event.remove(db,'before_commit',before_commit)

def _row(db,model,identifier,item):
    row=db.scalar(select(model).where(model.id==identifier,model.user_id==item.user_id,model.project_id==item.project_id)
        .execution_options(populate_existing=True))
    if row is None:fail('ASSISTANT_TARGET_NOT_FOUND','对象不属于当前项目',404)
    return row

def _snapshot(row):
    return {col.key:getattr(row,col.key) for col in inspect(row).mapper.column_attrs}

def change_versions(db,item,args):
    targets=[]
    if not args.checked():fail('ASSISTANT_CHANGE_INVALID','变更参数不完整或包含无关对象',422)
    if args.action=='confirm_candidates':
        for identifier in args.candidate_ids:
            row=_row(db,CandidateKnowledge,identifier,item)
            if str(row.review_status.value)!='pending':fail('ASSISTANT_TARGET_CHANGED','候选已处理')
            targets.append(('candidate',row))
            if row.payload['kind']=='relation':
                for key in ('source_candidate_id','target_candidate_id'):
                    targets.append(('candidate',_row(db,CandidateKnowledge,uuid.UUID(row.payload[key]),item)))
    elif args.action=='supersede':
        targets=[('entity',_row(db,KnowledgeEntity,i,item)) for i in (args.change.new_entity_id,args.change.old_entity_id)]
        targets.append(('evidence',_row(db,KnowledgeEvidence,args.change.evidence_id,item)))
    else:
        model=KnowledgeEntity if args.kind=='entity' else KnowledgeRelationship
        targets=[(args.kind,_row(db,model,args.knowledge_id,item))]
        if args.target_id:targets.append(('entity',_row(db,KnowledgeEntity,args.target_id,item)))
    # Bind complete rows and their evidence; later human approval revalidates the exact set.
    expanded=list(targets)
    for kind,row in targets:
        if kind in {'entity','relationship'}:
            owner=KnowledgeEvidence.entity_id if kind=='entity' else KnowledgeEvidence.relationship_id
            expanded.extend(('evidence',e) for e in db.scalars(select(KnowledgeEvidence).where(owner==row.id,
                KnowledgeEvidence.user_id==item.user_id,KnowledgeEvidence.project_id==item.project_id)))
    entity_ids={r.id for kind,r in targets if kind=='entity'}
    # Identity changes deliberately leave original entity rows intact. Bind their own history,
    # including new aliases/members, so an old proposal cannot silently change its meaning.
    if entity_ids:
        merges=list(db.scalars(select(EntityMerge).where(EntityMerge.user_id==item.user_id,EntityMerge.project_id==item.project_id,
            EntityMerge.source_id.in_(entity_ids)|EntityMerge.target_id.in_(entity_ids)).limit(501)))
        members=entity_ids|{m.source_id for m in merges}|{m.target_id for m in merges}
        expanded.extend(('merge',m) for m in merges)
        for kind,model,condition in [
            ('alias',EntityAlias,EntityAlias.entity_id.in_(members)),
            ('period',KnowledgePeriod,KnowledgePeriod.knowledge_id.in_(members)),
            ('change',KnowledgeChange,KnowledgeChange.new_entity_id.in_(members)|KnowledgeChange.old_entity_id.in_(members)),
            ('relationship',KnowledgeRelationship,KnowledgeRelationship.source_id.in_(members)|KnowledgeRelationship.target_id.in_(members))]:
            rows=list(db.scalars(select(model).where(model.user_id==item.user_id,model.project_id==item.project_id,condition).limit(501)))
            if len(rows)>500:fail('ASSISTANT_TARGET_TOO_LARGE','对象治理历史超过单次提案上限',422)
            expanded.extend((kind,r) for r in rows)
        if len(merges)>500:fail('ASSISTANT_TARGET_TOO_LARGE','对象身份历史超过单次提案上限',422)
    return sorted([dict(kind=k,id=str(r.id),sha256=digest(_snapshot(r))) for k,r in expanded],key=lambda x:(x['kind'],x['id']))

def propose(db,item,execution,identifier,kind,args):
    notes.lock_project(db,item.user_id,item.project_id);guard(db,item,execution,lock=True)
    payload=dict(arguments=args.model_dump(mode='json'))
    if kind=='propose_note_revision':
        current=notes.read(db,user_id=item.user_id,project_id=item.project_id,note_id=args.note_id).current
        if current.id!=args.expected_revision_id:fail('NOTE_REVISION_CONFLICT','所选笔记修订已过期')
        payload['before']=current.model_dump(mode='json')
    else:
        payload['versions']=change_versions(db,item,args)
        payload['before']=[dict(kind=v['kind'],record={k:value for k,value in _snapshot(_row(db,VERSION_MODELS[v['kind']],uuid.UUID(v['id']),item)).items()
            if k not in {'user_id','project_id'}}) for v in payload['versions']]
        payload=json.loads(json.dumps(payload,default=str))
    return payload

def execute(db,*,item,execution,identifier,kind,args,perform):
    input_hash=digest(dict(kind=kind,arguments=args.model_dump(mode='json')))
    op=db.get(AssistantOperation,identifier)
    if op:
        if (op.task_id,op.user_id,op.project_id)!=(item.id,item.user_id,item.project_id) or op.input_sha256!=input_hash:
            fail('ASSISTANT_OPERATION_CONFLICT','工具操作标识已绑定其他输入')
        if op.status not in {'executing','unknown'}:return dict(operation=public(op))
    else:
        guard(db,item,execution,lock=True)
        if len(operations(db,item))>=16:fail('AGENT_BUDGET_EXCEEDED','操作数量已达上限',429)
        pending=kind in {'propose_note_revision','propose_knowledge_change'}
        payload=propose(db,item,execution,identifier,kind,args) if pending else dict(arguments=args.model_dump(mode='json'))
        if len(json.dumps(payload,ensure_ascii=False))>200000:fail('ASSISTANT_PROPOSAL_TOO_LARGE','提案过大',422)
        bound=dict(task_id=str(item.id),user_id=str(item.user_id),project_id=str(item.project_id),kind=kind,payload=payload)
        op=AssistantOperation(id=identifier,task_id=item.id,user_id=item.user_id,project_id=item.project_id,kind=kind,
            input_sha256=input_hash,proposal_sha256=digest(bound),payload=payload,status='pending' if pending else 'executing')
        db.add(op);db.commit()
        if pending:return dict(operation=public(op))
    try:
        with fenced(db,item,execution):
            value=perform()
            if hasattr(value,'model_dump'):value=value.model_dump(mode='json')
            if len(json.dumps(value,ensure_ascii=False))>100000:fail('ASSISTANT_OPERATION_TOO_LARGE','操作结果过大',422)
            guard(db,item,execution,lock=True)
            op=db.get(AssistantOperation,identifier,populate_existing=True)
            op.status='succeeded';op.result=value;op.error_code=None
            for attempt in db.scalars(select(AssistantAttempt).where(AssistantAttempt.task_id==item.id,
                AssistantAttempt.agent!='project_assistant',AssistantAttempt.status=='started')):attempt.status='succeeded'
            db.commit()
    except AppError as exc:
        db.rollback()
        # A cancelled runner must not even publish an error receipt.
        guard(db,item,execution,lock=True)
        op=db.get(AssistantOperation,identifier,populate_existing=True)
        op.status='failed';op.error_code=exc.code;db.commit()
    return dict(operation=public(op))

def approve(db,*,user_id,project_id,task_id,request):
    from app.services.assistant_execution import _locked, _event
    notes.lock_project(db,user_id,project_id)
    task=_locked(db,user_id=user_id,project_id=project_id,task_id=task_id)
    old=db.get(AssistantApproval,request.request_id)
    fingerprint=digest(request.model_dump(mode='json'))
    if old:
        if (old.user_id,old.project_id,old.task_id)!=(user_id,project_id,task_id):fail('ASSISTANT_NOT_FOUND','审批不属于当前范围',404)
        if old.input_sha256!=fingerprint:fail('ASSISTANT_APPROVAL_CONFLICT','审批标识已绑定其他决定')
        db.commit();return
    op=db.get(AssistantOperation,request.operation_id,populate_existing=True)
    if op is None or (op.task_id,op.user_id,op.project_id)!=(task_id,user_id,project_id):fail('ASSISTANT_NOT_FOUND','提案不属于当前范围',404)
    if op.proposal_sha256!=request.proposal_sha256:fail('ASSISTANT_PROPOSAL_CONFLICT','提案校验值不匹配')
    bound=dict(task_id=str(task.id),user_id=str(user_id),project_id=str(project_id),kind=op.kind,payload=op.payload)
    if digest(bound)!=op.proposal_sha256 or digest(dict(kind=op.kind,arguments=op.payload.get('arguments')))!=op.input_sha256:
        fail('ASSISTANT_PROPOSAL_CONFLICT','提案内容或版本已变化')
    if task.status!='waiting_approval' or op.status!='pending':fail('ASSISTANT_NOT_APPROVABLE','任务或提案已处理，请刷新')
    if request.decision=='reject':op.status='rejected'
    else:
        try:
            # Services may commit internally; savepoints keep every mutation and receipt atomic.
            with Session(bind=db.connection(),expire_on_commit=False,join_transaction_mode='create_savepoint') as nested:
                if op.kind=='propose_note_revision':
                    args=op.payload['arguments']
                    result=notes.edit(nested,user_id=user_id,project_id=project_id,note_id=uuid.UUID(args['note_id']),
                        request=NoteEdit(request_id=op.id,**{k:v for k,v in args.items() if k!='note_id'}),
                        origin='assistant',task_id=task_id,provenance={'operation_id':str(op.id),'before_revision_id':args['expected_revision_id']})
                    outcome=result.model_dump(mode='json')
                else:
                    args=ChangeArgs.model_validate(op.payload['arguments'])
                    if change_versions(nested,task,args)!=op.payload['versions']:fail('ASSISTANT_TARGET_CHANGED','目标版本已变化，请重新生成提案')
                    outcome=_apply_change(nested,task,op.id,args)
            op.result=outcome;op.status='approved'
        except AppError as exc:
            db.rollback()
            notes.lock_project(db,user_id,project_id)
            task=_locked(db,user_id=user_id,project_id=project_id,task_id=task_id)
            op=db.get(AssistantOperation,request.operation_id,populate_existing=True)
            if task.status!='waiting_approval' or op.status!='pending':fail('ASSISTANT_NOT_APPROVABLE','任务或提案已被其他请求处理，请刷新')
            op.status='conflict';op.error_code=exc.code
    db.add(AssistantApproval(id=request.request_id,operation_id=op.id,task_id=task_id,user_id=user_id,
        project_id=project_id,input_sha256=fingerprint,decision=request.decision))
    task.revision+=1;_event(task,'approval','saved');db.commit()

def _apply_change(db,task,identifier,args):
    from app.services import knowledge, evolution, retirement, workspace
    from app.schemas.knowledge import ReviewResolve
    from app.schemas.retirement import RetirementCreate
    from app.schemas.workspace import OperationCreate
    scope=dict(user_id=task.user_id,project_id=task.project_id)
    if args.action=='confirm_candidates':
        candidates=[_row(db,CandidateKnowledge,i,task) for i in args.candidate_ids]
        candidates.sort(key=lambda r:(r.payload['kind']!='entity',str(r.id)))
        results=[]
        for row in candidates:
            results.append(knowledge._resolve_review(db,user_id=task.user_id,review_id=row.id,decision=ReviewResolve(action='confirm'),commit=False).model_dump(mode='json'))
            db.flush()
        db.commit();return dict(items=results)
    if args.action=='supersede':
        proposed=evolution.create_change(db,**scope,proposal=args.change)
        result=evolution.resolve_change(db,**scope,change_id=proposed.id,action='confirm')
    elif args.action=='retire':result=retirement.retire(db,**scope,request=RetirementCreate(request_id=identifier,
        kind=args.kind,knowledge_id=args.knowledge_id,category=args.category,reason=args.reason))
    else:result=workspace.operate(db,**scope,request=OperationCreate(request_id=identifier,action='merge',
        kind='entity',knowledge_id=args.knowledge_id,target_id=args.target_id,reason=args.reason))
    return result.model_dump(mode='json')

def save_artifact(db,*,user_id,project_id,task_id,artifact_id,request):
    from app.services.assistant_execution import read_artifact
    result=read_artifact(db,user_id=user_id,project_id=project_id,task_id=task_id,artifact_id=artifact_id)
    if not result.report:fail('ASSISTANT_REPORT_REQUIRED','该产物没有可编辑报告',422)
    report=result.report
    markdown='\n\n'.join(c.text for c in report.claims)
    if report.missing_information:markdown+='\n\n## 缺少信息\n'+'\n'.join(report.missing_information)
    return notes.create(db,user_id=user_id,project_id=project_id,request=NoteCreate(request_id=request.request_id,
        title=report.title,markdown=markdown),origin='assistant',task_id=task_id,
        provenance=dict(artifact_id=str(artifact_id),report=result.model_dump(mode='json')))
