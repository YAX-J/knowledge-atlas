"""Scoped application adapters for agents and coordinated workflows."""
from app.agents.base import SourceFile
from app.agents.code_analysis.context import CodeContext, CodeTask
from app.agents.runtime import RunContext, run_scope
from app.core.errors import AppError
from app.models.domain import SourceStatus
from app.services import code_context, ingestion
from app.services.projects import get_project
from app.services.agent_progress import RUN_LEASE_SECONDS, save_progress
from app.analysis.languages import CODE_SOURCE_TYPES
from app.agents.code_analysis.engine import LANGUAGE_FAMILIES

import hashlib
import json
import uuid
from datetime import timedelta, timezone
from sqlalchemy import func, select, update
from app.models.agent_run import AgentRun
from app.models.domain import CandidateKnowledge, Project, utc_now
from app.workflows.contracts import WorkflowList, WorkflowRead, WorkflowScopeRead


def aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _record(db,user_id,project_id,run_id):
    get_project(db,user_id=user_id,project_id=project_id)
    item=db.scalar(select(AgentRun).where(AgentRun.id==run_id,AgentRun.user_id==user_id,
        AgentRun.project_id==project_id).execution_options(populate_existing=True))
    if item is None:raise AppError(status_code=404,code='WORKFLOW_NOT_FOUND',message='协作任务不存在或不属于此项目')
    return item


def _counts(db,item):
    identifiers=[uuid.UUID(value) for value in (item.result or {}).get('candidate_ids',[])]
    if not identifiers:return {}
    rows=db.execute(select(CandidateKnowledge.review_status,func.count()).where(
        CandidateKnowledge.id.in_(identifiers),CandidateKnowledge.user_id==item.user_id,
        CandidateKnowledge.project_id==item.project_id,CandidateKnowledge.source_id==item.source_id,
        CandidateKnowledge.task_id==uuid.UUID(item.result['extraction_task_id']))
        .group_by(CandidateKnowledge.review_status))
    return {str(status):count for status,count in rows}


def read_run(db,*,user_id,project_id,run_id):
    item=_record(db,user_id,project_id,run_id)
    status=item.status
    if status=='running' and (item.lease_until is None or aware(item.lease_until)<=utc_now()):status='interrupted'
    request = item.request or {}
    question = item.kind == 'question_pipeline'
    include_code = bool(request.get('include_code_analysis', False))
    scope = WorkflowScopeRead(
        retrieval_mode=request.get('retrieval_mode', 'bm25') if question else None,
        valid_at=request.get('valid_at') if question else None,
        include_code_analysis=include_code,
        code_strategy=request.get('code_strategy', 'single_step') if include_code else None,
        snapshot_id=request.get('snapshot_id') if include_code else None,
        version_ids=(request.get('version_ids') or []) if include_code else [],
    )
    return WorkflowRead(id=item.id,project_id=item.project_id,source_id=item.source_id,kind=item.kind,status=status,
        result=item.result,events=item.events,usage=item.usage,error_code=item.error_code,
        created_at=item.created_at,updated_at=item.updated_at,review_counts=_counts(db,item),scope=scope)


def list_runs(db,*,user_id,project_id,page,page_size):
    get_project(db,user_id=user_id,project_id=project_id)
    query=select(AgentRun).where(AgentRun.user_id==user_id,AgentRun.project_id==project_id)
    total=db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items=list(db.scalars(query.order_by(AgentRun.created_at.desc(),AgentRun.id).offset((page-1)*page_size).limit(page_size)))
    return WorkflowList(items=[read_run(db,user_id=user_id,project_id=project_id,run_id=item.id) for item in items],
        total=total,page=page,page_size=page_size)


def start_run(db,*,user_id,project_id,request,settings):
    from app.services import knowledge, questions
    from app.workflows.routing import PIPELINES

    get_project(db,user_id=user_id,project_id=project_id)
    source=None
    if request.source_id:
        source=ingestion.get_source(db,user_id=user_id,source_id=request.source_id)
        if source.project_id!=project_id:raise AppError(status_code=404,code='SOURCE_NOT_FOUND',message='资料不属于此项目')
        if source.status!=SourceStatus.READY:raise AppError(status_code=409,code='SOURCE_NOT_PARSED',message='请先解析所选资料')
        if request.include_code_analysis and source.source_type not in CODE_SOURCE_TYPES:
            raise AppError(status_code=422,code='CALL_AGENT_UNAVAILABLE',message='代码分析需要支持的代码资料')
    data=request.model_dump(mode='json',exclude={'request_id'})
    data['source_sha256']=source.content_sha256 if source else None
    digest=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    db.execute(select(Project.id).where(Project.id==project_id,Project.user_id==user_id).with_for_update())
    existing=db.get(AgentRun,request.request_id)
    if existing:
        if existing.user_id!=user_id or existing.project_id!=project_id:
            raise AppError(status_code=404,code='WORKFLOW_NOT_FOUND',message='协作任务不存在或不属于此项目')
        if existing.input_sha256!=digest:raise AppError(status_code=409,code='WORKFLOW_REQUEST_CONFLICT',message='此任务标识已用于不同输入')
        db.commit()
        return read_run(db,user_id=user_id,project_id=project_id,run_id=existing.id)
    execution=uuid.uuid4()
    item=AgentRun(id=request.request_id,user_id=user_id,project_id=project_id,source_id=request.source_id,
        kind=request.kind,status='running',input_sha256=digest,request=data,events=[],usage={},
        execution_id=execution,lease_until=utc_now()+timedelta(seconds=RUN_LEASE_SECONDS))
    db.add(item);db.commit()
    runtime=RunContext(user_id=user_id,project_id=project_id,run_id=request.request_id,source_id=request.source_id,
        snapshot_id=request.snapshot_id,valid_at=request.valid_at.isoformat() if request.valid_at else None,
        model_limit=request.model_limit,tool_limit=request.tool_limit,embedding_limit=request.embedding_limit)
    partial_result = {}
    checkpoint_kinds = {'code_checkpoint', 'extraction_checkpoint', 'answer_checkpoint'}

    def persist(context):
        save_progress(db, context=context, execution_id=execution,
            result=partial_result if context.events[-1]['kind'] in checkpoint_kinds else None)

    def checkpoint(kind, values):
        partial_result.update(values)
        runtime.event(kind, 'saved')

    runtime.on_progress = persist
    code_source=request.include_code_analysis and source is not None and source.source_type in CODE_SOURCE_TYPES

    def code():
        if not code_source:return None
        result = analyze_code(db,settings=settings,user_id=user_id,source_id=request.source_id,strategy=request.code_strategy,
            snapshot_id=request.snapshot_id,version_ids=request.version_ids).model_dump(mode='json')
        checkpoint('code_checkpoint', {'code_analysis': result})
        return result

    def extract(code_result):
        # Only call metadata is a hint. Candidates must still quote this source's actual chunks.
        hint={'context':code_result['context'],'uncovered_calls':code_result['uncovered_call_count'],
            'calls':[dict(line=item['line'],expression=item['call_quote'],callee=item['callee_name'],resolution=item['resolution'])
                for item in code_result['calls'][:50]]} if code_result else {}
        result=knowledge.run_extraction(db,user_id=user_id,source_id=request.source_id,settings=settings,strategy='tools',code_findings=hint)
        if not result.task or result.task.status!='succeeded':
            error=result.task.error if result.task else {}
            raise AppError(status_code=502,code=(error or {}).get('code','EXTRACTION_FAILED'),message='候选整理未完成，请查看任务状态')
        ids=list(db.scalars(select(CandidateKnowledge.id).where(CandidateKnowledge.user_id==user_id,
            CandidateKnowledge.project_id==project_id,CandidateKnowledge.source_id==request.source_id,
            CandidateKnowledge.task_id==result.task.id).order_by(CandidateKnowledge.id)))
        result = dict(extraction_task_id=str(result.task.id),candidate_ids=[str(identifier) for identifier in ids],
            status='awaiting_review' if ids else 'succeeded')
        checkpoint('extraction_checkpoint', result)
        return result

    def answer(code_result=None):
        result = questions.answer_question(db,user_id=user_id,project_id=project_id,question=request.question,
            valid_at=request.valid_at,settings=settings,retrieval_mode=request.retrieval_mode,strategy='tools',
            code_findings={'context':code_result['context'],'calls':code_result['calls'][:20]} if code_result else None).model_dump(mode='json')
        checkpoint('answer_checkpoint', {'answer': result, 'status': 'succeeded'})
        return result

    result=None;error_code=None;status='failed'
    with run_scope(runtime):
        try:
            runtime.event('workflow','started')
            if request.kind=='knowledge_pipeline':result=PIPELINES[request.kind](code,extract)
            else:result=PIPELINES[request.kind](code,answer)
            status=result['status']
        except AppError as exc:
            db.rollback();error_code=exc.code
        except Exception:
            db.rollback();error_code='WORKFLOW_FAILED'
        runtime.event('workflow',status)
    changed=db.execute(update(AgentRun).where(AgentRun.id==request.request_id,AgentRun.user_id==user_id,
        AgentRun.project_id==project_id,AgentRun.status=='running',AgentRun.execution_id==execution,
        AgentRun.lease_until>utc_now()).values(status=status,result=result or partial_result or None,events=list(runtime.events),usage=runtime.usage(),
            error_code=error_code,execution_id=None,lease_until=None).execution_options(synchronize_session=False))
    if changed.rowcount!=1:
        db.rollback();raise AppError(status_code=409,code='WORKFLOW_INTERRUPTED',message='任务执行归属已失效，请读取已保存状态')
    db.commit()
    return read_run(db,user_id=user_id,project_id=project_id,run_id=request.request_id)


def resume_run(db,*,user_id,project_id,run_id):
    get_project(db,user_id=user_id,project_id=project_id)
    db.execute(select(Project.id).where(Project.id==project_id,Project.user_id==user_id).with_for_update())
    item=_record(db,user_id,project_id,run_id)
    if item.status=='succeeded':
        db.commit()
        return read_run(db,user_id=user_id,project_id=project_id,run_id=run_id)
    if item.status!='awaiting_review':raise AppError(status_code=409,code='WORKFLOW_NOT_WAITING',message='此任务未处于人工审核等待状态')
    source=ingestion.get_source(db,user_id=user_id,source_id=item.source_id)
    if source.project_id!=project_id or source.content_sha256!=item.request['source_sha256']:
        raise AppError(status_code=409,code='WORKFLOW_SOURCE_CHANGED',message='任务原文版本已变化')
    counts=_counts(db,item)
    if sum(counts.values())!=len(item.result['candidate_ids']):
        raise AppError(status_code=409,code='WORKFLOW_REVIEW_UNAVAILABLE',message='部分候选已不可用，请核对原文与审核记录')
    if counts.get('pending',0):raise AppError(status_code=409,code='WORKFLOW_REVIEW_PENDING',message='请先逐项确认或拒绝本任务的全部候选')
    item.status='succeeded'
    item.events=[*item.events,dict(sequence=len(item.events)+1,agent='workflow',kind='human_review',status='succeeded',elapsed_ms=0)]
    db.commit()
    return read_run(db,user_id=user_id,project_id=project_id,run_id=run_id)


def analyze_code(db,*,settings,user_id,source_id,strategy='single_step',snapshot_id=None,version_ids=None):
    source=ingestion.get_source(db,user_id=user_id,source_id=source_id)
    get_project(db,user_id=user_id,project_id=source.project_id)
    if source.source_type not in CODE_SOURCE_TYPES:
        raise AppError(status_code=409,code='CALL_AGENT_UNAVAILABLE',message='当前资料不是支持分析的代码文件')
    if source.status!=SourceStatus.READY:
        raise AppError(status_code=409,code='SOURCE_NOT_PARSED',message='请先完成代码资料解析')
    main,related,truncated,selection=code_context.select_context(db,source,LANGUAGE_FAMILIES[source.source_type],
        snapshot_id=snapshot_id,version_ids=version_ids)
    def freeze(item):
        return SourceFile(id=item.id,relative_path=item.relative_path or item.original_name,original_name=item.original_name,
            content=item.content,source_type=item.source_type,size_bytes=item.size_bytes)
    context=CodeContext(freeze(main),tuple(freeze(item) for item in related),settings,truncated,selection)
    from app.agents.registry import get_agent
    return get_agent('code_analysis').run(CodeTask(strategy),context)
