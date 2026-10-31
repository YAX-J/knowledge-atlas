"""Synchronous M1 tasks, scoped reads, durable reservations and read-only replay."""
from datetime import timedelta, timezone
import hashlib
import json
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import load_only

from app.agents.registry import get_agent
from app.agents.runtime import RunContext, run_scope
from app.analysis.languages import CODE_SOURCE_TYPES
from app.core.errors import AppError
from app.llm.providers.deepseek import CallAgentError
from app.models.assistant_task import AssistantTask
from app.models.graph import KnowledgeEvidence
from app.models.domain import Project, RepositorySnapshot, RepositorySnapshotFile, SourceChunk, SourceDocument, utc_now
from app.schemas.assistant import AssistantList, AssistantRead, AssistantResult, AssistantSummary, ReportClaim, ReportDraft
from app.services.agent_progress import RUN_LEASE_SECONDS, save_progress
from app.services.projects import get_project
from app.services.questions import collect_evidence
from app.services.search import search_knowledge
from app.tools.project import ProjectSource, ProjectTools


def _error(code, message, status=409):
    raise AppError(status_code=status, code=code, message=message)


def _status(item):
    lease = item.lease_until
    if item.status == 'running' and (lease is None or lease.replace(tzinfo=lease.tzinfo or timezone.utc) <= utc_now()):
        return 'interrupted'
    return item.status


def _summary(item):
    return dict(id=item.id, project_id=item.project_id, goal=item.request['goal'], status=_status(item),
        error_code=item.error_code, created_at=item.created_at, updated_at=item.updated_at)


def read_task(db, *, user_id, project_id, task_id):
    get_project(db, user_id=user_id, project_id=project_id)
    item = db.scalar(select(AssistantTask).where(AssistantTask.id == task_id,
        AssistantTask.user_id == user_id, AssistantTask.project_id == project_id).execution_options(populate_existing=True))
    if item is None:
        _error('ASSISTANT_NOT_FOUND', '助手任务不存在或不属于此项目', 404)
    return AssistantRead(**_summary(item), scope=item.request['scope'], result=item.result,
        events=item.events, usage=item.usage)


def list_tasks(db, *, user_id, project_id, page, page_size):
    get_project(db, user_id=user_id, project_id=project_id)
    filters = (AssistantTask.user_id == user_id, AssistantTask.project_id == project_id)
    total = db.scalar(select(func.count()).select_from(AssistantTask).where(*filters)) or 0
    items = db.scalars(select(AssistantTask).where(*filters).options(load_only(
        AssistantTask.id, AssistantTask.project_id, AssistantTask.request, AssistantTask.status,
        AssistantTask.error_code, AssistantTask.created_at, AssistantTask.updated_at, AssistantTask.lease_until))
        .order_by(AssistantTask.created_at.desc(), AssistantTask.id).offset((page - 1) * page_size).limit(page_size)
        .execution_options(populate_existing=True))
    return AssistantList(items=[AssistantSummary(**_summary(item)) for item in items], total=total, page=page, page_size=page_size)


def _freeze_sources(db, *, user_id, project_id, request):
    filters = (SourceDocument.user_id == user_id, SourceDocument.project_id == project_id,
               SourceDocument.id.in_(request.source_ids))
    metadata = list(db.execute(select(SourceDocument.id, SourceDocument.size_bytes, SourceDocument.status).where(*filters)))
    if len(metadata) != len(request.source_ids):
        _error('ASSISTANT_SOURCE_NOT_FOUND', '所选资料不存在或不属于此项目', 404)
    if any(row.status != 'ready' for row in metadata):
        _error('SOURCE_NOT_PARSED', '请先完成所选资料解析')
    if sum(row.size_bytes for row in metadata) > 200000:
        _error('ASSISTANT_SCOPE_TOO_LARGE', '所选原文超过 200000 字节，请缩小范围', 422)
    sources = list(db.scalars(select(SourceDocument).where(*filters).order_by(SourceDocument.id)))
    if sum(len(source.content.encode('utf-8')) for source in sources) > 200000:
        _error('ASSISTANT_SCOPE_TOO_LARGE', '所选原文超过大小限制', 422)
    chunks = list(db.scalars(select(SourceChunk).where(SourceChunk.user_id == user_id,
        SourceChunk.project_id == project_id, SourceChunk.source_id.in_(request.source_ids))
        .order_by(SourceChunk.source_id, SourceChunk.position).limit(501)))
    if len(chunks) > 500 or sum(len(chunk.content) for chunk in chunks) > 240000:
        _error('ASSISTANT_SCOPE_TOO_LARGE', '所选分块超过 500 块或文本限制', 422)
    frozen = [ProjectSource(source.id, user_id, project_id, source.relative_path or source.original_name,
        source.source_type, source.content, source.content_sha256,
        tuple((chunk.id, chunk.start_line, chunk.end_line, chunk.content) for chunk in chunks if chunk.source_id == source.id))
        for source in sources]
    paths = {}
    commit = None
    if request.snapshot_id:
        snapshot = db.scalar(select(RepositorySnapshot).where(RepositorySnapshot.id == request.snapshot_id,
            RepositorySnapshot.user_id == user_id, RepositorySnapshot.project_id == project_id))
        if snapshot is None:
            _error('ASSISTANT_SNAPSHOT_NOT_FOUND', '快照不存在或不属于此项目', 404)
        code_sources = [source for source in sources if source.source_type in CODE_SOURCE_TYPES]
        if not code_sources:
            _error('ASSISTANT_SNAPSHOT_INVALID', '固定快照需要选择其中的代码资料', 422)
        for source in code_sources:
            rows = list(db.scalars(select(RepositorySnapshotFile.path).where(
                RepositorySnapshotFile.snapshot_id == snapshot.id, RepositorySnapshotFile.source_id == source.id,
                RepositorySnapshotFile.status.notin_(['deleted', 'skipped'])).limit(2)))
            if source.repository_id != snapshot.repository_id or len(rows) != 1:
                _error('ASSISTANT_SNAPSHOT_INVALID', '所选代码版本没有唯一归属于指定快照')
            paths[source.id] = rows[0]
        commit = snapshot.commit_sha
    return frozen, paths, commit


def start_task(db, *, user_id, project_id, request, settings):
    get_project(db, user_id=user_id, project_id=project_id)
    data = request.model_dump(mode='json', exclude={'request_id'})
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    db.execute(select(Project.id).where(Project.id == project_id, Project.user_id == user_id).with_for_update())
    existing = db.get(AssistantTask, request.request_id)
    if existing is not None:
        if existing.user_id != user_id or existing.project_id != project_id:
            _error('ASSISTANT_NOT_FOUND', '助手任务不存在或不属于此项目', 404)
        if existing.input_sha256 != digest:
            _error('ASSISTANT_REQUEST_CONFLICT', '此任务标识已绑定不同目标、范围或预算')
        db.commit()
        return read_task(db, user_id=user_id, project_id=project_id, task_id=existing.id)
    sources, paths, commit = _freeze_sources(db, user_id=user_id, project_id=project_id, request=request)
    scope = dict(source_ids=[str(source.id) for source in sources],
        source_versions=[dict(id=str(source.id), sha256=source.content_sha256) for source in sources],
        snapshot_id=str(request.snapshot_id) if request.snapshot_id else None, commit_sha=commit,
        valid_at=data['valid_at'], retrieval_mode='bm25', capabilities=list(ProjectTools.contracts), embedding_limit=0,
        limits=dict(model=request.model_limit, tool=request.tool_limit, seconds=230,
                    coordinator_model=4, coordinator_tool=8, source_bytes=200000, chunks=500, references=32))
    execution = uuid.uuid4()
    item = AssistantTask(id=request.request_id, user_id=user_id, project_id=project_id, status='running',
        input_sha256=digest, request={**data, 'scope': scope}, events=[], usage={}, execution_id=execution,
        lease_until=utc_now() + timedelta(seconds=RUN_LEASE_SECONDS))
    db.add(item)
    db.commit()
    runtime = RunContext(user_id=user_id, project_id=project_id, run_id=request.request_id,
        model_limit=request.model_limit, tool_limit=request.tool_limit, embedding_limit=0, seconds=230)
    result = None

    def persist(context):
        save_progress(db, context=context, execution_id=execution, record_model=AssistantTask,
            result=result.model_dump(mode='json') if result is not None else None)

    def search(query, gateway):
        found = search_knowledge(db, user_id=user_id, project_id=project_id, query=query, types=[],
            valid_at=request.valid_at, top_k=5, mode='bm25', settings=settings)
        evidence, summary = collect_evidence(found)
        references = []
        truncated = summary.truncated
        for record in evidence.values():
            source = db.scalar(select(SourceDocument).where(SourceDocument.id == record.source_id,
                SourceDocument.user_id == user_id, SourceDocument.project_id == project_id))
            chunk = db.scalar(select(SourceChunk).where(SourceChunk.id == record.chunk_id,
                SourceChunk.source_id == record.source_id, SourceChunk.user_id == user_id, SourceChunk.project_id == project_id))
            if source is None or chunk is None or record.quote not in chunk.content:
                continue
            frozen = ProjectSource(source.id, user_id, project_id, source.relative_path or source.original_name,
                source.source_type, '', source.content_sha256, ())
            ref = gateway._reference(frozen, record.start_line, record.end_line, record.quote,
                chunk_id=chunk.id, evidence_id=record.id)
            if ref:
                references.append(ref)
            else:
                truncated = True
        return dict(references=references, truncated=truncated)

    gateway = ProjectTools(run_id=request.request_id, sources=sources, search=search,
        snapshot_id=request.snapshot_id, commit_sha=commit, snapshot_paths=paths)
    runtime.on_progress = persist
    status, error_code = 'failed', None
    with run_scope(runtime):
        try:
            runtime.event('assistant', 'started')
            # Empty projects can report missing input without a paid request.
            has_knowledge = bool(db.scalar(select(KnowledgeEvidence.id).where(
                KnowledgeEvidence.user_id == user_id, KnowledgeEvidence.project_id == project_id).limit(1)))
            if not sources and not has_knowledge:
                result = AssistantResult(action='finish', report=ReportDraft(title='缺少项目材料', claims=[ReportClaim(
                    text='当前范围没有可读取的资料或已确认知识证据。', status='uncertain', reference_ids=[])],
                    missing_information=['请选择已解析的文档/代码版本，或先审核项目知识。']))
            else:
                result = get_agent('project_assistant').run(request, dict(settings=settings, tools=gateway, scope=scope))
            runtime.event('report_checkpoint', 'saved')
            status = 'succeeded'
        except AppError as exc:
            db.rollback()
            error_code = exc.code
        except CallAgentError as exc:
            db.rollback()
            error_code = exc.code
        except Exception:
            db.rollback()
            error_code = 'ASSISTANT_FAILED'
        runtime.event('assistant', status)
    changed = db.execute(update(AssistantTask).where(AssistantTask.id == request.request_id,
        AssistantTask.user_id == user_id, AssistantTask.project_id == project_id,
        AssistantTask.status == 'running', AssistantTask.execution_id == execution, AssistantTask.lease_until > utc_now(),
        AssistantTask.project_id.in_(select(Project.id).where(Project.user_id == user_id, Project.archived_at.is_(None))))
        .values(status=status, result=result.model_dump(mode='json') if result is not None else None,
            events=list(runtime.events), usage=runtime.usage(), error_code=error_code, execution_id=None, lease_until=None)
        .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        _error('ASSISTANT_INTERRUPTED', '执行归属已失效，请读取已保存状态')
    db.commit()
    return read_task(db, user_id=user_id, project_id=project_id, task_id=request.request_id)
