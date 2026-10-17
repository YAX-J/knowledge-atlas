import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.domain import ProcessingTask, SourceDocument, TaskStatus
from app.services.projects import get_project


ALLOWED_SUFFIXES = {".md", ".markdown"}


async def create_source_and_task(
    db: Session,
    *,
    settings: Settings,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    upload: UploadFile,
    source_type: str | None,
) -> tuple[SourceDocument, ProcessingTask]:
    get_project(db, user_id=user_id, project_id=project_id)

    original_name = Path(upload.filename or "").name
    if not original_name or Path(original_name).suffix.lower() not in ALLOWED_SUFFIXES:
        raise AppError(
            status_code=415,
            code="UNSUPPORTED_SOURCE_TYPE",
            message="当前阶段仅支持 Markdown 文件",
            details={"allowed_extensions": sorted(ALLOWED_SUFFIXES)},
        )

    normalized_source_type = (source_type or "markdown").strip().lower()
    if normalized_source_type != "markdown":
        raise AppError(
            status_code=422,
            code="SOURCE_TYPE_INVALID",
            message="文件类型与当前导入能力不匹配",
            details={"source_type": normalized_source_type},
        )

    raw_content = await upload.read(settings.max_upload_bytes + 1)
    if len(raw_content) > settings.max_upload_bytes:
        raise AppError(
            status_code=413,
            code="SOURCE_TOO_LARGE",
            message="上传文件超过大小限制",
            details={"max_bytes": settings.max_upload_bytes},
        )

    try:
        content = raw_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AppError(
            status_code=422,
            code="SOURCE_ENCODING_INVALID",
            message="Markdown 文件必须使用 UTF-8 编码",
        ) from exc

    if not content.strip():
        raise AppError(
            status_code=422,
            code="SOURCE_EMPTY",
            message="上传文件不能为空",
        )

    source = SourceDocument(
        user_id=user_id,
        project_id=project_id,
        original_name=original_name,
        media_type=upload.content_type or "text/markdown",
        source_type=normalized_source_type,
        size_bytes=len(raw_content),
        content_sha256=hashlib.sha256(raw_content).hexdigest(),
        content=content,
    )
    task = ProcessingTask(
        user_id=user_id,
        project_id=project_id,
        source=source,
        type="knowledge_extraction",
        status=TaskStatus.QUEUED,
        stage="uploaded",
        progress=0,
    )
    db.add_all([source, task])
    db.commit()
    db.refresh(source)
    db.refresh(task)
    return source, task


def get_source(
    db: Session, *, user_id: uuid.UUID, source_id: uuid.UUID
) -> SourceDocument:
    source = db.scalar(
        select(SourceDocument).where(
            SourceDocument.id == source_id,
            SourceDocument.user_id == user_id,
        )
    )
    if source is None:
        raise AppError(
            status_code=404,
            code="SOURCE_NOT_FOUND",
            message="资料不存在",
            details={"source_id": str(source_id)},
        )
    return source


def get_task(
    db: Session, *, user_id: uuid.UUID, task_id: uuid.UUID
) -> ProcessingTask:
    task = db.scalar(
        select(ProcessingTask).where(
            ProcessingTask.id == task_id,
            ProcessingTask.user_id == user_id,
        )
    )
    if task is None:
        raise AppError(
            status_code=404,
            code="TASK_NOT_FOUND",
            message="处理任务不存在",
            details={"task_id": str(task_id)},
        )
    return task

