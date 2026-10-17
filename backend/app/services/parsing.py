import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.domain import (
    ProcessingTask,
    SourceChunk,
    SourceStatus,
    TaskStatus,
    utc_now,
)
from app.services.ingestion import get_source, get_task
from app.services.markdown import parse_markdown


def run_task(db: Session, *, user_id: uuid.UUID, task_id: uuid.UUID) -> ProcessingTask:
    task = get_task(db, user_id=user_id, task_id=task_id)
    if task.status == TaskStatus.SUCCEEDED:
        return task
    source = get_source(db, user_id=user_id, source_id=task.source_id)
    if (
        source.project_id != task.project_id
        or source.source_type != "markdown"
        or task.type not in {"markdown_parsing", "knowledge_extraction"}
    ):
        raise AppError(
            status_code=409, code="TASK_TYPE_UNSUPPORTED",
            message="此任务不支持 Markdown 解析",
        )

    claimed = db.execute(
        update(ProcessingTask)
        .where(
            ProcessingTask.id == task_id,
            ProcessingTask.user_id == user_id,
            ProcessingTask.status.in_([TaskStatus.QUEUED, TaskStatus.FAILED]),
        )
        .values(
            status=TaskStatus.RUNNING, stage="parsing", progress=0,
            error=None, started_at=utc_now(), completed_at=None,
        )
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
    source.status = SourceStatus.PROCESSING
    db.commit()

    try:
        chunks = parse_markdown(source.content, source_id=source.id)
        db.execute(delete(SourceChunk).where(
            SourceChunk.source_id == source.id,
            SourceChunk.user_id == user_id,
            SourceChunk.project_id == source.project_id,
        ))
        db.add_all([
            SourceChunk(
                id=chunk.id, user_id=user_id, project_id=source.project_id,
                source_id=source.id, position=chunk.position, kind=chunk.kind,
                heading_path=chunk.heading_path, start_line=chunk.start_line,
                end_line=chunk.end_line, content=chunk.content,
                content_sha256=chunk.content_sha256,
            ) for chunk in chunks
        ])
        source.status = SourceStatus.READY
        task.status = TaskStatus.SUCCEEDED
        task.stage = "parsed"
        task.progress = 100
        task.completed_at = utc_now()
        db.commit()
    except Exception:
        db.rollback()
        # Do not expose raw document text or database errors through task state.
        source.status = SourceStatus.FAILED
        task.status = TaskStatus.FAILED
        task.stage = "parsing"
        task.progress = 0
        task.error = {
            "code": "SOURCE_PARSE_FAILED", "message": "Markdown 解析失败，可重试任务"
        }
        task.completed_at = utc_now()
        db.commit()
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
