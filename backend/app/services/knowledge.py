"""Explicit extraction, human review, and transactional formal knowledge promotion."""

import json
import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.domain import (
    CandidateKnowledge, ProcessingTask, Project, ReviewEvent, ReviewStatus,
    SourceChunk, SourceDocument, SourceStatus, TaskStatus, utc_now,
)
from app.schemas.knowledge import ExtractionRead, FactValidity, RelationDraft, ReviewBatchRead, ReviewBatchResolve, ReviewEndpointRead, ReviewRead, ReviewResolve
from app.schemas.tasks import TaskRead
from app.services import deepseek, fact_time, graph, relationship_replacement
from app.services.ingestion import get_source
from app.services.projects import get_project


EXTRACTION_TASK_TYPE = "knowledge_candidates"


def extraction_task_id(source_id: uuid.UUID, strategy='single_step', note_revision_id: uuid.UUID | None = None, plan_sha256: str | None = None) -> uuid.UUID:
    version = deepseek.PROMPT_VERSION + (':tools-v1' if strategy == 'tools' else '')
    if strategy == 'batched':
        version += f':batched-v1:{plan_sha256}'
    if note_revision_id is not None:
        version += f':note:{note_revision_id}'
    return uuid.uuid5(source_id, version)


def lease_is_active(expires_at: datetime | None, now: datetime) -> bool:
    if expires_at is None:
        return True
    # SQLite omits offsets; PostgreSQL may return a non-UTC session timezone.
    expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    return expiry > now


def _source(db: Session, user_id: uuid.UUID, source_id: uuid.UUID) -> SourceDocument:
    source = get_source(db, user_id=user_id, source_id=source_id)
    get_project(db, user_id=user_id, project_id=source.project_id)
    return source


def _batch_plan(db, source, settings):
    from app.services.extraction_batches import build_plan, MAX_CHUNKS
    if source.status != SourceStatus.READY:
        raise AppError(status_code=409,code='SOURCE_NOT_PARSED',message='请先完成资料解析')
    chunks=list(db.scalars(select(SourceChunk).where(SourceChunk.source_id==source.id,
        SourceChunk.user_id==source.user_id,SourceChunk.project_id==source.project_id)
        .order_by(SourceChunk.position).limit(MAX_CHUNKS+1)))
    return build_plan(source,chunks,settings)


def extraction_plan(db, *, user_id, source_id, settings):
    source=_source(db,user_id,source_id)
    plan=_batch_plan(db,source,settings)
    task_id=extraction_task_id(source.id,'batched',plan_sha256=plan.public['plan_sha256'])
    current=get_extraction(db,user_id=user_id,source_id=source.id,task_id=task_id)
    return {**plan.public,'cached':bool(current.task and current.task.status==TaskStatus.SUCCEEDED)}


def get_extraction(db: Session, *, user_id: uuid.UUID, source_id: uuid.UUID, task_id: uuid.UUID | None = None) -> ExtractionRead:
    source = _source(db, user_id, source_id)
    query = select(ProcessingTask).where(
        ProcessingTask.user_id == user_id,
        ProcessingTask.project_id == source.project_id,
        ProcessingTask.source_id == source.id,
        ProcessingTask.type == EXTRACTION_TASK_TYPE,
    )
    if task_id is not None:
        query = query.where(ProcessingTask.id == task_id)
    task = db.scalar(query.order_by(ProcessingTask.created_at.desc(), ProcessingTask.id)
                     .limit(1).execution_options(populate_existing=True))
    counts = {'pending': 0, 'confirmed': 0, 'rejected': 0}
    rows = db.execute(select(CandidateKnowledge.review_status, func.count()).where(
        CandidateKnowledge.task_id == task.id,
        CandidateKnowledge.user_id == user_id,
        CandidateKnowledge.project_id == source.project_id,
        CandidateKnowledge.source_id == source.id,
    ).group_by(CandidateKnowledge.review_status)).all() if task else []
    for status, count in rows:
        counts[status.value if isinstance(status, ReviewStatus) else status] = count
    return ExtractionRead(task=TaskRead.model_validate(task) if task else None,
                          candidate_count=sum(counts.values()), review_counts=counts)


def run_extraction(
    db: Session, *, user_id: uuid.UUID, source_id: uuid.UUID, settings: Settings, strategy='single_step', code_findings=None,
    note_revision_id: uuid.UUID | None = None, temporal_reference: datetime | None = None,
    approved_plan_sha256: str | None = None,
) -> ExtractionRead:
    source = _source(db, user_id, source_id)
    # Serialize short claims only. The model call runs after this transaction commits.
    db.execute(select(SourceDocument.id).where(
        SourceDocument.id == source.id, SourceDocument.user_id == user_id,
        SourceDocument.project_id == source.project_id,
    ).with_for_update())
    if strategy not in {'single_step','tools','batched'}:
        raise AppError(status_code=422,code='EXTRACTION_STRATEGY_INVALID',message='不支持的抽取策略')
    batch_plan = None
    if strategy == 'batched':
        batch_plan = _batch_plan(db, source, settings)
        if approved_plan_sha256 != batch_plan.public['plan_sha256']:
            raise AppError(status_code=409,code='EXTRACTION_PLAN_CHANGED',message='分批计划已变化，请重新预览后确认')
    task_id = extraction_task_id(source.id, strategy, note_revision_id,
        batch_plan.public['plan_sha256'] if batch_plan else None)
    current = get_extraction(db, user_id=user_id, source_id=source.id, task_id=task_id)
    if current.task and current.task.status == TaskStatus.SUCCEEDED:
        db.commit()
        return current
    now = utc_now()
    task = db.get(ProcessingTask, task_id)
    if task and task.status == TaskStatus.RUNNING and lease_is_active(task.lease_expires_at, now):
        raise AppError(status_code=409, code="EXTRACTION_RUNNING", message="知识提取正在执行，请稍后刷新候选状态")
    if source.status != SourceStatus.READY:
        raise AppError(status_code=409, code="SOURCE_NOT_PARSED", message="请先完成资料解析")
    if not settings.deepseek_api_key or not settings.deepseek_api_key.get_secret_value().strip():
        raise AppError(status_code=503, code="EXTRACTION_NOT_CONFIGURED", message="请先在后端 .env 中配置 DEEPSEEK_API_KEY 并重启后端")
    chunks = list(db.scalars(select(SourceChunk).where(
        SourceChunk.user_id == user_id, SourceChunk.project_id == source.project_id,
        SourceChunk.source_id == source.id,
    ).order_by(SourceChunk.position).limit(801 if batch_plan else 101)))
    if not chunks:
        raise AppError(status_code=409, code="SOURCE_HAS_NO_CHUNKS", message="资料没有可提取的原文分块")
    model_input = [{"chunk_id": str(chunk.id), "content": chunk.content} for chunk in chunks]
    evidence_chunks = {chunk.id: {
        "content": chunk.content, "start_line": chunk.start_line,
        "heading_path": list(chunk.heading_path),
    } for chunk in chunks}
    if batch_plan:
        evidence_chunks = batch_plan.evidence
    if not batch_plan and (len(chunks) > 100 or len(json.dumps({"chunks": model_input}, ensure_ascii=False)) > settings.extraction_max_input_chars):
        raise AppError(status_code=413, code="EXTRACTION_INPUT_TOO_LARGE", message="资料超过单次提取限制，请拆分为较小的文件")
    execution_id = uuid.uuid4()
    if task is None:
        task = ProcessingTask(
            id=task_id, user_id=user_id,
            project_id=source.project_id, source_id=source.id, type=EXTRACTION_TASK_TYPE,
            attempt_count=0,
        )
        db.add(task)
    task.status = TaskStatus.RUNNING
    task.stage = "extracting"
    task.progress = 0
    task.error = None
    task.started_at = now
    task.completed_at = None
    task.execution_id = execution_id
    task.lease_expires_at = now + timedelta(seconds=max(
        settings.task_lease_seconds, math.ceil(settings.deepseek_timeout_seconds) * (len(batch_plan.batches) if batch_plan else 1) + 60,
    ))
    task.attempt_count += 1
    db.commit()

    # The network call receives snapshots, without holding the source claim lock.
    records: list[CandidateKnowledge] = []
    error: dict[str, str] | None = None
    try:
        from app.agents.registry import get_agent
        if batch_plan:
            from app.services.extraction_batches import invoke_batches
            def before_batch(index, total):
                owned = db.execute(update(ProcessingTask).where(ProcessingTask.id == task.id,
                    ProcessingTask.user_id == user_id, ProcessingTask.project_id == source.project_id,
                    ProcessingTask.status == TaskStatus.RUNNING, ProcessingTask.execution_id == execution_id,
                ).values(progress=math.floor(index / total * 90),
                    lease_expires_at=utc_now()+timedelta(seconds=max(settings.task_lease_seconds,math.ceil(settings.deepseek_timeout_seconds)+60)))
                    .execution_options(synchronize_session=False))
                if owned.rowcount != 1:
                    db.rollback()
                    raise AppError(status_code=409,code='EXTRACTION_REPLACED',message='提取已被接手，已停止后续批次')
                db.commit()
            result = invoke_batches(batch_plan,settings,task.id,before_batch)
        else:
            result = get_agent('knowledge_extraction').run(strategy,dict(settings=settings,chunks=model_input,code_findings=code_findings))
        ids = {draft.local_id: uuid.uuid5(task.id, draft.local_id)
               for draft in [*result.entities, *result.relations]}
        entities = {draft.local_id: draft for draft in result.entities}
        for draft in [*result.entities, *result.relations]:
            evidence = []
            for reference in draft.evidence:
                chunk = evidence_chunks.get(reference.chunk_id)
                if chunk is None or reference.quote not in chunk["content"]:
                    raise deepseek.ExtractionError("EXTRACTION_EVIDENCE_INVALID", "模型证据与原文不一致，本次结果未保存，请重试")
                # Locate the actual quote inside its chunk; never trust model line numbers.
                start = chunk["content"].index(reference.quote)
                start_line = chunk["start_line"] + chunk["content"][:start].count("\n")
                evidence.append({
                    "chunk_id": str(chunk.get('chunk_id', reference.chunk_id)), "quote": reference.quote,
                    "start_line": start_line,
                    "end_line": start_line + reference.quote.count("\n"),
                    "heading_path": chunk["heading_path"],
                })
            relation = isinstance(draft, RelationDraft)
            payload = {
                "kind": "relation" if relation else "entity",
                "local_id": draft.local_id, "evidence": evidence,
                "model": settings.deepseek_model, "prompt_version": deepseek.PROMPT_VERSION+(':tools-v1' if strategy=='tools' else ':batched-v1' if batch_plan else ''),
            }
            if draft.temporal is not None:
                expressions = [draft.temporal.start, draft.temporal.end]
                if any(expression and not any(expression in entry["quote"] for entry in evidence)
                       for expression in expressions):
                    raise deepseek.ExtractionError("EXTRACTION_TIME_EVIDENCE_INVALID", "候选的时间表述未出现在引用原文中")
                validity = fact_time.proposed_validity(draft.temporal, temporal_reference)
                payload.update(
                    temporal=draft.temporal.model_dump(mode="json"),
                    temporal_reference=temporal_reference.isoformat() if temporal_reference else None,
                    validity=validity.model_dump(mode="json") if validity else None,
                )
            if relation:
                if draft.fact_slot and relationship_replacement.supported(
                    draft.type, entities[draft.target].type, entities[draft.source].name, entities[draft.target].name,
                    [entry["quote"] for entry in evidence],
                ):
                    payload["fact_slot"] = draft.fact_slot
                payload.update(source_candidate_id=str(ids[draft.source]), target_candidate_id=str(ids[draft.target]))
                name = f"{entities[draft.source].name} → {entities[draft.target].name}"[:255]
            else:
                name = draft.name
            records.append(CandidateKnowledge(
                id=ids[draft.local_id], user_id=user_id, project_id=source.project_id,
                source_id=source.id, task_id=task.id, candidate_type=draft.type,
                name=name, summary=draft.summary, confidence=draft.confidence,
                payload=payload, review_status=ReviewStatus.PENDING,
            ))
    except deepseek.ExtractionError as exc:
        error = {"code": exc.code, "message": exc.message}
    except AppError as exc:
        # A shared budget failure must release the extraction lease as a failed task.
        error = {'code':exc.code,'message':exc.message}
    try:
        finished = db.execute(update(ProcessingTask).where(
            ProcessingTask.id == task.id, ProcessingTask.user_id == user_id,
            ProcessingTask.project_id == source.project_id, ProcessingTask.source_id == source.id,
            ProcessingTask.status == TaskStatus.RUNNING, ProcessingTask.execution_id == execution_id,
        ).values(
            status=TaskStatus.FAILED if error else TaskStatus.SUCCEEDED,
            stage="extracting" if error else "candidates_ready",
            progress=0 if error else 100, error=error, completed_at=utc_now(),
            execution_id=None, lease_expires_at=None,
        ).execution_options(synchronize_session=False))
        if finished.rowcount != 1:
            db.rollback()
            raise AppError(status_code=409, code="EXTRACTION_REPLACED", message="本次提取已被新的执行接手，请刷新候选状态")
        if not error:
            db.add_all(records)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_extraction(db, user_id=user_id, source_id=source.id, task_id=task_id)


def _review_query(user_id: uuid.UUID):
    return select(CandidateKnowledge).join(
        Project, Project.id == CandidateKnowledge.project_id,
    ).join(SourceDocument, SourceDocument.id == CandidateKnowledge.source_id).join(
        ProcessingTask, ProcessingTask.id == CandidateKnowledge.task_id,
    ).where(
        CandidateKnowledge.user_id == user_id, Project.user_id == user_id,
        Project.archived_at.is_(None), SourceDocument.user_id == user_id,
        SourceDocument.project_id == CandidateKnowledge.project_id,
        ProcessingTask.user_id == user_id,
        ProcessingTask.project_id == CandidateKnowledge.project_id,
        ProcessingTask.source_id == CandidateKnowledge.source_id,
        ProcessingTask.type == EXTRACTION_TASK_TYPE,
        ProcessingTask.status == TaskStatus.SUCCEEDED,
    )


def read_review(candidate: CandidateKnowledge, knowledge_id: uuid.UUID | None = None) -> ReviewRead:
    return ReviewRead(
        id=candidate.id, project_id=candidate.project_id, source_id=candidate.source_id,
        task_id=candidate.task_id, kind=candidate.payload["kind"], type=candidate.candidate_type,
        name=candidate.name, summary=candidate.summary, confidence=candidate.confidence,
        review_status=candidate.review_status, evidence=candidate.payload["evidence"],
        temporal=candidate.payload.get("temporal"),
        temporal_reference=candidate.payload.get("temporal_reference"),
        validity=candidate.payload.get("validity"),
        supersedes_relationship_id=(candidate.payload.get("replacement") or {}).get("old_relationship_id"),
        knowledge_id=knowledge_id,
        source_candidate_id=candidate.payload.get("source_candidate_id"),
        target_candidate_id=candidate.payload.get("target_candidate_id"),
        created_at=candidate.created_at, updated_at=candidate.updated_at,
    )


def list_reviews(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID,
    source_id: uuid.UUID | None, review_status: ReviewStatus | None,
    candidate_type: str | None, min_confidence: float | None, page: int, page_size: int,
    kind: str | None = None, text_query: str = '',
) -> tuple[list[ReviewRead], int]:
    get_project(db, user_id=user_id, project_id=project_id)
    query = _review_query(user_id).where(CandidateKnowledge.project_id == project_id)
    if source_id is not None:
        source = _source(db, user_id, source_id)
        if source.project_id != project_id:
            raise AppError(status_code=404, code="SOURCE_NOT_FOUND", message="资料不存在")
        query = query.where(CandidateKnowledge.source_id == source_id)
    if review_status is not None:
        query = query.where(CandidateKnowledge.review_status == review_status)
    if candidate_type is not None:
        query = query.where(CandidateKnowledge.candidate_type == candidate_type)
    if min_confidence is not None:
        query = query.where(CandidateKnowledge.confidence >= min_confidence)
    if kind is not None:
        query = query.where(CandidateKnowledge.payload['kind'].as_string() == kind)
    normalized = ' '.join(text_query.split())
    if normalized:
        query = query.where(or_(CandidateKnowledge.name.icontains(normalized, autoescape=True),
                               CandidateKnowledge.summary.icontains(normalized, autoescape=True)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(
        case((CandidateKnowledge.payload["kind"].as_string() == "entity", 0), else_=1),
        CandidateKnowledge.created_at, CandidateKnowledge.id,
    ).offset((page - 1) * page_size).limit(page_size)))
    ids = graph.knowledge_ids(db, items)
    result = [read_review(item, ids.get(item.id)) for item in items]
    # Fetch at most two endpoint IDs per listed relation, independent of list filters.
    endpoint_ids = {endpoint for item in result if item.kind == 'relation'
                    for endpoint in (item.source_candidate_id, item.target_candidate_id) if endpoint is not None}
    endpoints = {}
    if endpoint_ids:
        endpoints = {(item.task_id, item.source_id, item.id): item for item in db.scalars(
            _review_query(user_id).where(CandidateKnowledge.project_id == project_id,
                                        CandidateKnowledge.id.in_(endpoint_ids),
                                        CandidateKnowledge.payload['kind'].as_string() == 'entity'))}
    for item in result:
        if item.kind != 'relation':
            continue
        for endpoint_id in dict.fromkeys((item.source_candidate_id, item.target_candidate_id)):
            endpoint = endpoints.get((item.task_id, item.source_id, endpoint_id))
            if endpoint is not None:
                item.endpoints.append(ReviewEndpointRead(id=endpoint.id, name=endpoint.name, review_status=endpoint.review_status))
    for candidate, item in zip(items, result):
        if item.review_status == ReviewStatus.PENDING and candidate.payload.get("fact_slot"):
            scoped_endpoints = {str(identifier): endpoints.get((item.task_id, item.source_id, identifier))
                                for identifier in (item.source_candidate_id, item.target_candidate_id)}
            item.replacement, item.replacement_issue = relationship_replacement.preview(
                db, candidate, scoped_endpoints, item.validity,
            )
    return result, total


def resolve_review(
    db: Session, *, user_id: uuid.UUID, review_id: uuid.UUID, decision: ReviewResolve,
) -> ReviewRead:
    try:
        return _resolve_review(db, user_id=user_id, review_id=review_id, decision=decision)
    except Exception:
        db.rollback()
        raise


def _resolve_review(
    db: Session, *, user_id: uuid.UUID, review_id: uuid.UUID, decision: ReviewResolve, commit: bool = True,
) -> ReviewRead:
    candidate = db.scalar(_review_query(user_id).where(CandidateKnowledge.id == review_id))
    if candidate is None:
        raise AppError(status_code=404, code="REVIEW_NOT_FOUND", message="候选知识不存在")
    # A project lock also orders relationship decisions against endpoint decisions.
    db.execute(select(Project.id).where(
        Project.id == candidate.project_id, Project.user_id == user_id,
    ).with_for_update())
    db.refresh(candidate)
    target_status = ReviewStatus.CONFIRMED if decision.action == "confirm" else ReviewStatus.REJECTED
    changes = decision.changes.model_dump(exclude={"validity"}, exclude_none=True)
    validity_changed = "validity" in decision.changes.model_fields_set
    validity = decision.changes.validity
    saved_validity = FactValidity.model_validate(candidate.payload["validity"]) if candidate.payload.get("validity") else None
    replacement_receipt = decision.replacement.model_dump(mode="json") if decision.replacement else None
    if candidate.review_status != ReviewStatus.PENDING:
        if (candidate.review_status != target_status
                or any(getattr(candidate, key) != value for key, value in changes.items())
                or (validity_changed and saved_validity != validity)
                or (replacement_receipt is not None and candidate.payload.get("replacement") != replacement_receipt)):
            raise AppError(status_code=409, code="REVIEW_ALREADY_RESOLVED", message="候选已处理，请刷新状态；当前不支持撤回或改判")
    endpoint_candidates = []
    if target_status == ReviewStatus.CONFIRMED and candidate.payload["kind"] == "relation":
        try:
            endpoints = {uuid.UUID(candidate.payload[key]) for key in ("source_candidate_id", "target_candidate_id")}
        except (KeyError, ValueError, TypeError) as exc:
            raise graph._promotion_error() from exc
        endpoint_candidates = list(db.scalars(_review_query(user_id).where(
            CandidateKnowledge.id.in_(endpoints), CandidateKnowledge.task_id == candidate.task_id,
            CandidateKnowledge.review_status == ReviewStatus.CONFIRMED,
        )))
        if {item.id for item in endpoint_candidates} != endpoints:
            raise AppError(status_code=409, code="REVIEW_ENDPOINTS_UNCONFIRMED", message="请先确认关系两端的实体；已拒绝的实体不能组成已确认关系")
    if candidate.review_status != ReviewStatus.PENDING:
        formal_id = graph.promote_candidate(db, candidate, endpoint_candidates) if target_status == ReviewStatus.CONFIRMED else None
        if commit:
            db.commit()
        return read_review(candidate, formal_id)
    replacement = None
    if target_status == ReviewStatus.CONFIRMED:
        normalized_validity = validity if validity_changed else saved_validity
        replacement, issue = relationship_replacement.preview(
            db, candidate, {str(item.id): item for item in endpoint_candidates}, normalized_validity,
        )
        if decision.replacement and (
            replacement is None or replacement.approval != decision.replacement or validity_changed or changes
        ):
            raise AppError(status_code=409, code="REVIEW_REPLACEMENT_STALE",
                           message="替代建议已变化，请刷新并重新核对原文和时间")
        if replacement and not decision.replacement:
            raise AppError(status_code=409, code="REVIEW_REPLACEMENT_REQUIRED",
                           message="请核对新旧原文并单独确认替代")
        if issue:
            raise AppError(status_code=409, code="REVIEW_PRIMARY_DATABASE_CONFLICT",
                           message="已有主数据库记录与候选重叠，请核对服务、数据库及生效时间")
    before = {"name": candidate.name, "summary": candidate.summary, "review_status": candidate.review_status.value}
    values = {**changes, "review_status": target_status, "updated_at": utc_now()}
    prior_validity = candidate.payload.get("validity")
    if validity_changed or replacement_receipt:
        values["payload"] = dict(candidate.payload)
        if validity_changed:
            values["payload"]["validity"] = validity.model_dump(mode="json") if validity else None
        if replacement_receipt:
            values["payload"]["replacement"] = replacement_receipt
    updated = db.execute(update(CandidateKnowledge).where(
        CandidateKnowledge.id == review_id, CandidateKnowledge.user_id == user_id,
        CandidateKnowledge.project_id == candidate.project_id,
        CandidateKnowledge.review_status == ReviewStatus.PENDING,
    ).values(**values).execution_options(synchronize_session=False))
    if updated.rowcount != 1:
        db.rollback()
        raise AppError(status_code=409, code="REVIEW_ALREADY_RESOLVED", message="候选已被其他操作处理，请刷新状态")
    db.refresh(candidate)
    after = {"name": candidate.name, "summary": candidate.summary, "review_status": candidate.review_status.value}
    if validity_changed or prior_validity is not None:
        before["validity"] = prior_validity
        after["validity"] = candidate.payload.get("validity")
    formal_id = graph.promote_candidate(
        db, candidate, endpoint_candidates,
        canonical_source_id=replacement.old_relationship.source_id if replacement else None,
    ) if target_status == ReviewStatus.CONFIRMED else None
    if replacement:
        before["replacement"], after["replacement"] = graph.apply_relationship_replacement(
            db, replacement.old_relationship.id, formal_id, replacement.effective_at,
        )
    db.add(ReviewEvent(
        candidate_id=candidate.id, user_id=user_id, project_id=candidate.project_id,
        action=decision.action, before=before,
        after=after,
    ))
    if commit:
        db.commit()
    return read_review(candidate, formal_id)


def resolve_reviews_batch(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, decision: ReviewBatchResolve,
) -> ReviewBatchRead:
    try:
        get_project(db, user_id=user_id, project_id=project_id)
        db.execute(select(Project.id).where(
            Project.id == project_id, Project.user_id == user_id, Project.archived_at.is_(None),
        ).with_for_update())
        candidates = list(db.scalars(_review_query(user_id).where(
            CandidateKnowledge.project_id == project_id,
            CandidateKnowledge.source_id == decision.source_id,
            CandidateKnowledge.id.in_(decision.review_ids),
        ).execution_options(populate_existing=True)))
        if {item.id for item in candidates} != set(decision.review_ids):
            raise AppError(status_code=404, code='REVIEW_NOT_FOUND', message='所选候选不存在或不属于当前项目资料，请刷新后重试')
        # Caller selection order does not affect endpoint dependencies.
        candidates.sort(key=lambda item: (item.payload['kind'] != 'entity', str(item.id)))
        resolved = {}
        for candidate in candidates:
            resolved[candidate.id] = _resolve_review(
                db, user_id=user_id, review_id=candidate.id,
                decision=ReviewResolve(action=decision.action), commit=False,
            )
            db.flush()
        db.commit()
        return ReviewBatchRead(items=[resolved[item] for item in decision.review_ids], processed_count=len(resolved))
    except Exception:
        db.rollback()
        raise
