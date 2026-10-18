"""Explicit extraction, human review, and transactional formal knowledge promotion."""

import json
import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.domain import (
    CandidateKnowledge, ProcessingTask, Project, ReviewEvent, ReviewStatus,
    SourceChunk, SourceDocument, SourceStatus, TaskStatus, utc_now,
)
from app.schemas.knowledge import ExtractionRead, RelationDraft, ReviewRead, ReviewResolve
from app.schemas.tasks import TaskRead
from app.services import deepseek, graph
from app.services.ingestion import get_source
from app.services.projects import get_project


EXTRACTION_TASK_TYPE = "knowledge_candidates"


def extraction_task_id(source_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(source_id, deepseek.PROMPT_VERSION)


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


def get_extraction(db: Session, *, user_id: uuid.UUID, source_id: uuid.UUID) -> ExtractionRead:
    source = _source(db, user_id, source_id)
    task = db.scalar(select(ProcessingTask).where(
        ProcessingTask.id == extraction_task_id(source.id),
        ProcessingTask.user_id == user_id,
        ProcessingTask.project_id == source.project_id,
        ProcessingTask.source_id == source.id,
        ProcessingTask.type == EXTRACTION_TASK_TYPE,
    ).execution_options(populate_existing=True))
    count = db.scalar(select(func.count()).select_from(CandidateKnowledge).where(
        CandidateKnowledge.task_id == task.id,
        CandidateKnowledge.user_id == user_id,
        CandidateKnowledge.project_id == source.project_id,
        CandidateKnowledge.source_id == source.id,
    )) if task else 0
    return ExtractionRead(task=TaskRead.model_validate(task) if task else None, candidate_count=count or 0)


def run_extraction(
    db: Session, *, user_id: uuid.UUID, source_id: uuid.UUID, settings: Settings,
) -> ExtractionRead:
    source = _source(db, user_id, source_id)
    # Serialize short claims only. The model call runs after this transaction commits.
    db.execute(select(SourceDocument.id).where(
        SourceDocument.id == source.id, SourceDocument.user_id == user_id,
        SourceDocument.project_id == source.project_id,
    ).with_for_update())
    current = get_extraction(db, user_id=user_id, source_id=source.id)
    if current.task and current.task.status == TaskStatus.SUCCEEDED:
        db.commit()
        return current
    now = utc_now()
    task = db.get(ProcessingTask, extraction_task_id(source.id))
    if task and task.status == TaskStatus.RUNNING and lease_is_active(task.lease_expires_at, now):
        raise AppError(status_code=409, code="EXTRACTION_RUNNING", message="知识提取正在执行，请稍后刷新候选状态")
    if source.status != SourceStatus.READY:
        raise AppError(status_code=409, code="SOURCE_NOT_PARSED", message="请先完成资料解析")
    if not settings.deepseek_api_key or not settings.deepseek_api_key.get_secret_value().strip():
        raise AppError(status_code=503, code="EXTRACTION_NOT_CONFIGURED", message="请先在后端 .env 中配置 DEEPSEEK_API_KEY 并重启后端")
    chunks = list(db.scalars(select(SourceChunk).where(
        SourceChunk.user_id == user_id, SourceChunk.project_id == source.project_id,
        SourceChunk.source_id == source.id,
    ).order_by(SourceChunk.position).limit(101)))
    if not chunks:
        raise AppError(status_code=409, code="SOURCE_HAS_NO_CHUNKS", message="资料没有可提取的原文分块")
    model_input = [{"chunk_id": str(chunk.id), "content": chunk.content} for chunk in chunks]
    evidence_chunks = {chunk.id: {
        "content": chunk.content, "start_line": chunk.start_line,
        "heading_path": list(chunk.heading_path),
    } for chunk in chunks}
    if len(chunks) > 100 or len(json.dumps({"chunks": model_input}, ensure_ascii=False)) > settings.extraction_max_input_chars:
        raise AppError(status_code=413, code="EXTRACTION_INPUT_TOO_LARGE", message="资料超过单次提取限制，请拆分为较小的文件")
    execution_id = uuid.uuid4()
    if task is None:
        task = ProcessingTask(
            id=extraction_task_id(source.id), user_id=user_id,
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
        settings.task_lease_seconds, math.ceil(settings.deepseek_timeout_seconds) + 60,
    ))
    task.attempt_count += 1
    db.commit()

    # The network call receives snapshots, without holding the source claim lock.
    records: list[CandidateKnowledge] = []
    error: dict[str, str] | None = None
    try:
        result = deepseek.extract_candidates(settings, model_input)
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
                    "chunk_id": str(reference.chunk_id), "quote": reference.quote,
                    "start_line": start_line,
                    "end_line": start_line + reference.quote.count("\n"),
                    "heading_path": chunk["heading_path"],
                })
            relation = isinstance(draft, RelationDraft)
            payload = {
                "kind": "relation" if relation else "entity",
                "local_id": draft.local_id, "evidence": evidence,
                "model": settings.deepseek_model, "prompt_version": deepseek.PROMPT_VERSION,
            }
            if relation:
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
    return get_extraction(db, user_id=user_id, source_id=source.id)


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
        knowledge_id=knowledge_id,
        source_candidate_id=candidate.payload.get("source_candidate_id"),
        target_candidate_id=candidate.payload.get("target_candidate_id"),
        created_at=candidate.created_at, updated_at=candidate.updated_at,
    )


def list_reviews(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID,
    source_id: uuid.UUID | None, review_status: ReviewStatus | None,
    candidate_type: str | None, min_confidence: float | None, page: int, page_size: int,
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
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.order_by(
        case((CandidateKnowledge.payload["kind"].as_string() == "entity", 0), else_=1),
        CandidateKnowledge.created_at, CandidateKnowledge.id,
    ).offset((page - 1) * page_size).limit(page_size)))
    ids = graph.knowledge_ids(db, items)
    return [read_review(item, ids.get(item.id)) for item in items], total


def resolve_review(
    db: Session, *, user_id: uuid.UUID, review_id: uuid.UUID, decision: ReviewResolve,
) -> ReviewRead:
    try:
        return _resolve_review(db, user_id=user_id, review_id=review_id, decision=decision)
    except Exception:
        db.rollback()
        raise


def _resolve_review(
    db: Session, *, user_id: uuid.UUID, review_id: uuid.UUID, decision: ReviewResolve,
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
    changes = decision.changes.model_dump(exclude_none=True)
    if candidate.review_status != ReviewStatus.PENDING:
        if candidate.review_status != target_status or any(getattr(candidate, key) != value for key, value in changes.items()):
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
        db.commit()
        return read_review(candidate, formal_id)
    before = {"name": candidate.name, "summary": candidate.summary, "review_status": candidate.review_status.value}
    values = {**changes, "review_status": target_status, "updated_at": utc_now()}
    updated = db.execute(update(CandidateKnowledge).where(
        CandidateKnowledge.id == review_id, CandidateKnowledge.user_id == user_id,
        CandidateKnowledge.project_id == candidate.project_id,
        CandidateKnowledge.review_status == ReviewStatus.PENDING,
    ).values(**values).execution_options(synchronize_session=False))
    if updated.rowcount != 1:
        db.rollback()
        raise AppError(status_code=409, code="REVIEW_ALREADY_RESOLVED", message="候选已被其他操作处理，请刷新状态")
    db.refresh(candidate)
    db.add(ReviewEvent(
        candidate_id=candidate.id, user_id=user_id, project_id=candidate.project_id,
        action=decision.action, before=before,
        after={"name": candidate.name, "summary": candidate.summary, "review_status": candidate.review_status.value},
    ))
    formal_id = graph.promote_candidate(db, candidate, endpoint_candidates) if target_status == ReviewStatus.CONFIRMED else None
    db.commit()
    return read_review(candidate, formal_id)
