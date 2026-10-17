import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.models.domain import (
    ProcessingTask,
    SourceChunk,
    SourceDocument,
    SourceStatus,
    TaskStatus,
    utc_now,
)
from app.services.ingestion import get_source, get_task
from app.services.markdown import MarkdownChunk, parse_markdown
from app.services.projects import get_project


PARSING_TASK_TYPES = ("markdown_parsing", "knowledge_extraction")
logger = logging.getLogger(__name__)


def expired_task_filter(now: datetime, lease_seconds: int) -> ColumnElement[bool]:
    return and_(
        ProcessingTask.status == TaskStatus.RUNNING,
        or_(
            ProcessingTask.lease_expires_at <= now,
            and_(
                ProcessingTask.lease_expires_at.is_(None),
                func.coalesce(ProcessingTask.started_at, ProcessingTask.updated_at)
                <= now - timedelta(seconds=lease_seconds),
            ),
        ),
    )


def _finish_task(
    db: Session, *, task: ProcessingTask, execution_id: uuid.UUID,
    chunks: list[MarkdownChunk] | None,
) -> bool:
    succeeded = chunks is not None
    result = db.execute(
        update(ProcessingTask).where(
            ProcessingTask.id == task.id,
            ProcessingTask.user_id == task.user_id,
            ProcessingTask.project_id == task.project_id,
            ProcessingTask.status == TaskStatus.RUNNING,
            ProcessingTask.execution_id == execution_id,
        ).values(
            status=TaskStatus.SUCCEEDED if succeeded else TaskStatus.FAILED,
            stage="parsed" if succeeded else "parsing",
            progress=100 if succeeded else 0,
            error=None if succeeded else {
                "code": "SOURCE_PARSE_FAILED", "message": "Markdown 解析失败，可重试任务"
            },
            completed_at=utc_now(), execution_id=None, lease_expires_at=None,
        ).execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        # A replacement execution owns this task. It alone may write results.
        db.rollback()
        return False
    if chunks is not None:
        db.execute(delete(SourceChunk).where(
            SourceChunk.source_id == task.source_id,
            SourceChunk.user_id == task.user_id,
            SourceChunk.project_id == task.project_id,
        ))
        db.add_all([
            SourceChunk(
                id=chunk.id, user_id=task.user_id, project_id=task.project_id,
                source_id=task.source_id, position=chunk.position, kind=chunk.kind,
                heading_path=chunk.heading_path, start_line=chunk.start_line,
                end_line=chunk.end_line, content=chunk.content,
                content_sha256=chunk.content_sha256,
            ) for chunk in chunks
        ])
    db.execute(update(SourceDocument).where(
        SourceDocument.id == task.source_id,
        SourceDocument.user_id == task.user_id,
        SourceDocument.project_id == task.project_id,
    ).values(status=SourceStatus.READY if succeeded else SourceStatus.FAILED))
    db.commit()
    return True


def run_task(
    db: Session, *, user_id: uuid.UUID, task_id: uuid.UUID,
    settings: Settings | None = None,
    recover_expired: bool = False, retry_failed: bool = True,
) -> ProcessingTask:
    settings = settings or get_settings()
    task = get_task(db, user_id=user_id, task_id=task_id)
    if task.status == TaskStatus.SUCCEEDED:
        return task
    source = get_source(db, user_id=user_id, source_id=task.source_id)
    get_project(db, user_id=user_id, project_id=task.project_id)
    if (
        source.project_id != task.project_id
        or source.source_type != "markdown"
        or task.type not in PARSING_TASK_TYPES
    ):
        raise AppError(
            status_code=409, code="TASK_TYPE_UNSUPPORTED",
            message="此任务不支持 Markdown 解析",
        )

    now = utc_now()
    if recover_expired and task.attempt_count >= settings.task_max_attempts:
        exhausted = db.execute(
            update(ProcessingTask).where(
                ProcessingTask.id == task_id, ProcessingTask.user_id == user_id,
                expired_task_filter(now, settings.task_lease_seconds),
                ProcessingTask.attempt_count >= settings.task_max_attempts,
            ).values(
                status=TaskStatus.FAILED, stage="parsing", progress=0,
                error={"code": "TASK_ATTEMPTS_EXHAUSTED", "message": "处理多次中断，请手动重试解析"},
                completed_at=now, execution_id=None, lease_expires_at=None,
            ).execution_options(synchronize_session=False)
        )
        if exhausted.rowcount == 1:
            db.execute(update(SourceDocument).where(
                SourceDocument.id == source.id,
                SourceDocument.user_id == user_id,
                SourceDocument.project_id == task.project_id,
            ).values(status=SourceStatus.FAILED))
            db.commit()
            db.refresh(task)
            return task
    statuses = [TaskStatus.QUEUED]
    if retry_failed:
        statuses.append(TaskStatus.FAILED)
    eligible = ProcessingTask.status.in_(statuses)
    if recover_expired:
        eligible = or_(eligible, and_(
            expired_task_filter(now, settings.task_lease_seconds),
            ProcessingTask.attempt_count < settings.task_max_attempts,
        ))
    execution_id = uuid.uuid4()
    claimed = db.execute(
        update(ProcessingTask)
        .where(
            ProcessingTask.id == task_id,
            ProcessingTask.user_id == user_id,
            eligible,
        )
        .values(
            status=TaskStatus.RUNNING, stage="parsing", progress=0,
            error=None, started_at=now, completed_at=None,
            execution_id=execution_id,
            lease_expires_at=now + timedelta(seconds=settings.task_lease_seconds),
            attempt_count=ProcessingTask.attempt_count + 1,
        ).execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        db.rollback()
        # Another request may have completed while this one was claiming.
        db.refresh(task)
        if task.status == TaskStatus.SUCCEEDED:
            return task
        raise AppError(
            status_code=409, code="TASK_NOT_RUNNABLE", message="任务正在执行或已取消"
        )
    db.execute(update(SourceDocument).where(
        SourceDocument.id == source.id,
        SourceDocument.user_id == user_id,
        SourceDocument.project_id == task.project_id,
    ).values(status=SourceStatus.PROCESSING))
    db.commit()

    try:
        chunks = parse_markdown(source.content, source_id=source.id)
        _finish_task(db, task=task, execution_id=execution_id, chunks=chunks)
    except Exception as error:
        db.rollback()
        logger.warning("parse_failed task_id=%s error_type=%s", task_id, type(error).__name__)
        _finish_task(db, task=task, execution_id=execution_id, chunks=None)
    db.refresh(task)
    return task


def list_chunks(
    db: Session, *, user_id: uuid.UUID, source_id: uuid.UUID,
    page: int, page_size: int,
) -> tuple[list[SourceChunk], int]:
    source = get_source(db, user_id=user_id, source_id=source_id)
    filters = (
        SourceChunk.user_id == user_id,
        SourceChunk.project_id == source.project_id,
        SourceChunk.source_id == source_id,
    )
    total = db.scalar(select(func.count()).select_from(SourceChunk).where(*filters)) or 0
    items = db.scalars(
        select(SourceChunk).where(*filters)
        .order_by(SourceChunk.position)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return list(items), total
