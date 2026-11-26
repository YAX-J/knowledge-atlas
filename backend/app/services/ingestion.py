import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, load_only, selectinload

from app.core.config import Settings
from app.core.errors import AppError
from app.models.domain import (
    ProcessingTask,
    Project,
    SourceDocument,
    SourceStatus,
    TaskStatus,
)
from app.services.projects import get_project
from app.services.repositories import get_repository
from app.services.source_languages import MEDIA_TYPE_BY_SOURCE, SOURCE_TYPE_BY_SUFFIX, TASK_TYPE_BY_SOURCE, TASK_TYPES_BY_SOURCE


PARSING_TASK_TYPES = ("markdown_parsing", "knowledge_extraction", "code_parsing")
MAX_RELATIVE_PATH_LENGTH = 1024
MAX_RELATED_JAVA_BYTES = 20 * 1024 * 1024


def normalize_relative_path(relative_path: str | None, *, original_name: str) -> str | None:
    if relative_path is None or not relative_path.strip():
        return None

    normalized = relative_path.strip().replace("\\", "/")
    parts = normalized.split("/")
    drive_prefixed = len(normalized) >= 3 and normalized[0].isalpha() and normalized[1:3] == ":/"
    if (
        len(normalized) > MAX_RELATIVE_PATH_LENGTH
        or normalized.startswith("/")
        or drive_prefixed
        or any(not part or part in {".", ".."} or "\x00" in part for part in parts)
        or parts[-1] != original_name
    ):
        raise AppError(
            status_code=422,
            code="SOURCE_PATH_INVALID",
            message="资料相对路径无效",
            details={"max_length": MAX_RELATIVE_PATH_LENGTH},
        )
    return normalized


async def create_source_and_task(
    db: Session,
    *,
    settings: Settings,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    upload: UploadFile,
    source_type: str | None,
    relative_path: str | None,
    repository_id: uuid.UUID | None,
) -> tuple[SourceDocument, ProcessingTask]:
    raw_content = await upload.read(settings.max_upload_bytes + 1)
    source, task, _ = create_source_and_task_from_bytes(
        db,
        settings=settings,
        user_id=user_id,
        project_id=project_id,
        filename=upload.filename or "",
        raw_content=raw_content,
        source_type=source_type,
        relative_path=relative_path,
        repository_id=repository_id,
    )
    return source, task


def create_source_and_task_from_bytes(
    db: Session,
    *,
    settings: Settings,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    filename: str,
    raw_content: bytes,
    source_type: str | None,
    relative_path: str | None,
    repository_id: uuid.UUID | None,
) -> tuple[SourceDocument, ProcessingTask, bool]:
    get_project(db, user_id=user_id, project_id=project_id)
    repository = (
        get_repository(
            db,
            user_id=user_id,
            project_id=project_id,
            repository_id=repository_id,
        )
        if repository_id is not None else None
    )

    original_name = Path(filename.replace("\\", "/")).name
    suffix = Path(original_name).suffix.lower()
    inferred_source_type = SOURCE_TYPE_BY_SUFFIX.get(suffix)
    if not original_name or inferred_source_type is None:
        raise AppError(
            status_code=415,
            code="UNSUPPORTED_SOURCE_TYPE",
            message="支持 Markdown 及 Java、Python、JavaScript/JSX、TypeScript/TSX、Go、C、C++、C# 源文件",
            details={"allowed_extensions": sorted(SOURCE_TYPE_BY_SUFFIX)},
        )

    normalized_relative_path = normalize_relative_path(
        relative_path, original_name=original_name
    )
    if repository is not None and normalized_relative_path is None:
        raise AppError(
            status_code=422,
            code="SOURCE_REPOSITORY_PATH_REQUIRED",
            message="仓库资料必须提供仓库内相对路径",
        )

    normalized_source_type = (source_type or inferred_source_type).strip().lower()
    if normalized_source_type != inferred_source_type:
        raise AppError(
            status_code=422,
            code="SOURCE_TYPE_INVALID",
            message="文件类型与当前导入能力不匹配",
            details={"source_type": normalized_source_type},
        )

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
            message="文本资料必须使用 UTF-8 编码",
        ) from exc

    if not content.strip():
        raise AppError(
            status_code=422,
            code="SOURCE_EMPTY",
            message="上传文件不能为空",
        )

    content_sha256 = hashlib.sha256(raw_content).hexdigest()
    # Serialize concurrent uploads within this user's project on PostgreSQL.
    db.execute(
        select(Project.id)
        .where(Project.id == project_id, Project.user_id == user_id)
        .with_for_update()
    )
    repository_filter = (
        SourceDocument.repository_id == repository.id
        if repository is not None
        else SourceDocument.repository_id.is_(None)
    )
    existing = db.execute(
        select(SourceDocument, ProcessingTask)
        .join(ProcessingTask, ProcessingTask.source_id == SourceDocument.id)
        .where(
            SourceDocument.user_id == user_id,
            SourceDocument.project_id == project_id,
            SourceDocument.source_type == normalized_source_type,
            SourceDocument.content_sha256 == content_sha256,
            repository_filter,
            # A content hash identifies bytes, not a file location. Unlocated
            # single-file uploads retain their historical content-only identity.
            (SourceDocument.relative_path == normalized_relative_path
             if normalized_relative_path is not None
             else SourceDocument.relative_path.is_(None)),
            ProcessingTask.user_id == user_id,
            ProcessingTask.project_id == project_id,
            ProcessingTask.type.in_(TASK_TYPES_BY_SOURCE[normalized_source_type]),
        )
        .order_by(
            SourceDocument.created_at, SourceDocument.id,
            ProcessingTask.created_at.desc(), ProcessingTask.id,
        )
        .limit(1)
    ).first()
    if existing is not None:
        db.commit()
        return existing[0], existing[1], True

    source = SourceDocument(
        user_id=user_id,
        project_id=project_id,
        repository_id=repository.id if repository is not None else None,
        original_name=original_name,
        relative_path=normalized_relative_path,
        media_type=MEDIA_TYPE_BY_SOURCE[normalized_source_type],
        source_type=normalized_source_type,
        size_bytes=len(raw_content),
        content_sha256=content_sha256,
        content=content,
    )
    task = ProcessingTask(
        user_id=user_id,
        project_id=project_id,
        source=source,
        type=TASK_TYPE_BY_SOURCE[normalized_source_type],
        status=TaskStatus.QUEUED,
        stage="uploaded",
        progress=0,
    )
    db.add_all([source, task])
    db.commit()
    db.refresh(source)
    db.refresh(task)
    return source, task, False


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


def list_sources(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID,
    page: int, page_size: int,
    text_query: str = '', source_type: str | None = None, source_status: SourceStatus | None = None, archived: bool = False,
) -> tuple[list[tuple[SourceDocument, ProcessingTask | None]], int]:
    get_project(db, user_id=user_id, project_id=project_id)
    filters = [
        SourceDocument.user_id == user_id,
        SourceDocument.project_id == project_id,
    ]
    from app.services.library import archived_source_condition
    archive_filter = archived_source_condition()
    filters.append(archive_filter if archived else ~archive_filter)
    query = ' '.join(text_query.split())
    if query:
        filters.append(or_(SourceDocument.original_name.icontains(query, autoescape=True),
                           SourceDocument.relative_path.icontains(query, autoescape=True)))
    if source_type is not None:
        filters.append(SourceDocument.source_type == source_type)
    if source_status is not None:
        filters.append(SourceDocument.status == source_status)
    total = db.scalar(select(func.count()).select_from(SourceDocument).where(*filters)) or 0
    sources = list(db.scalars(
        select(SourceDocument).where(*filters)
        .options(load_only(
            SourceDocument.id, SourceDocument.project_id, SourceDocument.repository_id,
            SourceDocument.original_name, SourceDocument.relative_path, SourceDocument.source_type,
            SourceDocument.size_bytes, SourceDocument.status, SourceDocument.created_at, SourceDocument.updated_at,
            raiseload=True,
        ), selectinload(SourceDocument.repository))
        .order_by(SourceDocument.created_at.desc(), SourceDocument.id)
        .offset((page - 1) * page_size).limit(page_size)
    ))
    latest_tasks: dict[uuid.UUID, ProcessingTask] = {}
    if sources:
        ranked = select(ProcessingTask.id, func.row_number().over(
            partition_by=ProcessingTask.source_id,
            order_by=(ProcessingTask.created_at.desc(), ProcessingTask.id.desc()),
        ).label('position')).where(
            ProcessingTask.user_id == user_id, ProcessingTask.project_id == project_id,
            ProcessingTask.source_id.in_([source.id for source in sources]),
            ProcessingTask.type.in_(PARSING_TASK_TYPES),
        ).subquery()
        tasks = db.scalars(
            select(ProcessingTask).join(ranked, ranked.c.id == ProcessingTask.id).where(ranked.c.position == 1)
            .options(load_only(ProcessingTask.id, ProcessingTask.source_id, ProcessingTask.status, raiseload=True))
        )
        for task in tasks:
            latest_tasks.setdefault(task.source_id, task)
    return [(source, latest_tasks.get(source.id)) for source in sources], total


def list_ready_java_sources(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    repository_id: uuid.UUID | None,
    exclude_source_id: uuid.UUID,
    limit: int,
) -> tuple[list[SourceDocument], bool]:
    repository_filter = (
        SourceDocument.repository_id == repository_id
        if repository_id is not None
        else SourceDocument.repository_id.is_(None)
    )
    metadata = list(db.execute(
        select(SourceDocument.id, SourceDocument.size_bytes).where(
            SourceDocument.user_id == user_id,
            SourceDocument.project_id == project_id,
            SourceDocument.source_type == "java",
            SourceDocument.status == SourceStatus.READY,
            SourceDocument.id != exclude_source_id,
            repository_filter,
        )
        .order_by(SourceDocument.created_at, SourceDocument.id)
        .limit(limit + 1)
    ))
    selected_ids: list[uuid.UUID] = []
    selected_bytes = 0
    truncated = len(metadata) > limit
    for source_id, size_bytes in metadata[:limit]:
        if selected_bytes + size_bytes > MAX_RELATED_JAVA_BYTES:
            truncated = True
            break
        selected_ids.append(source_id)
        selected_bytes += size_bytes
    if not selected_ids:
        return [], truncated
    records_by_id = {
        item.id: item for item in db.scalars(
            select(SourceDocument).where(SourceDocument.id.in_(selected_ids))
        )
    }
    return [records_by_id[source_id] for source_id in selected_ids], truncated


def get_task(
    db: Session, *, user_id: uuid.UUID, task_id: uuid.UUID
) -> ProcessingTask:
    task = db.scalar(
        select(ProcessingTask).where(
            ProcessingTask.id == task_id,
            ProcessingTask.user_id == user_id,
        ).execution_options(populate_existing=True)
    )
    if task is None:
        raise AppError(
            status_code=404,
            code="TASK_NOT_FOUND",
            message="处理任务不存在",
            details={"task_id": str(task_id)},
        )
    return task

