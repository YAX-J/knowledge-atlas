import uuid

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.domain import SourceStatus
from app.schemas.sources import (
    JavaCallRead,
    JavaCrossFileCallRead,
    JavaRelatedMethodRead,
    JavaRelatedTypeRead,
    JavaStructureRead,
    JavaSymbolRead,
    JavaTypeRelationshipRead,
    SourceChunkList,
    SourceChunkRead,
    SourceRead,
    SourceList,
    SourceListItem,
    SourceUploadResponse,
)
from app.services import ingestion, parsing
from app.services.java_source import JavaSourceInput, analyze_java
from app.services.source_links import github_file_urls


router = APIRouter(tags=["sources"])


@router.get("/projects/{project_id}/sources", response_model=SourceList)
def list_sources(
    project_id: uuid.UUID,
    db: DatabaseSession,
    user_id: CurrentUserId,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SourceList:
    records, total = ingestion.list_sources(
        db, user_id=user_id, project_id=project_id, page=page, page_size=page_size
    )
    git_urls = github_file_urls(
        db,
        user_id=user_id,
        project_id=project_id,
        source_ids=[source.id for source, _ in records],
    )
    items = []
    for source, task in records:
        item = SourceListItem.model_validate(source)
        item.repository_name = source.repository.name if source.repository else None
        item.git_url = git_urls.get(source.id)
        item.task_id = task.id if task else None
        item.task_status = task.status if task else None
        items.append(item)
    return SourceList(items=items, page=page, page_size=page_size, total=total)


@router.post(
    "/projects/{project_id}/sources",
    response_model=SourceUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_source(
    project_id: uuid.UUID,
    db: DatabaseSession,
    user_id: CurrentUserId,
    file: UploadFile = File(...),
    source_type: str | None = Form(default=None),
    relative_path: str | None = Form(default=None),
    repository_id: uuid.UUID | None = Form(default=None),
) -> SourceUploadResponse:
    source, task = await ingestion.create_source_and_task(
        db,
        settings=get_settings(),
        user_id=user_id,
        project_id=project_id,
        upload=file,
        source_type=source_type,
        relative_path=relative_path,
        repository_id=repository_id,
    )
    return SourceUploadResponse(
        source_id=source.id,
        task_id=task.id,
        status=task.status.value,
    )


@router.get("/sources/{source_id}", response_model=SourceRead)
def get_source(
    source_id: uuid.UUID,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> SourceRead:
    source = ingestion.get_source(db, user_id=user_id, source_id=source_id)
    git_url = github_file_urls(
        db,
        user_id=user_id,
        project_id=source.project_id,
        source_ids=[source.id],
    ).get(source.id)
    return SourceRead(
        id=source.id,
        project_id=source.project_id,
        repository_id=source.repository_id,
        repository_name=source.repository.name if source.repository else None,
        git_url=git_url,
        original_name=source.original_name,
        relative_path=source.relative_path,
        media_type=source.media_type,
        source_type=source.source_type,
        size_bytes=source.size_bytes,
        content_sha256=source.content_sha256,
        status=source.status,
        content_preview=source.content[:4000],
        line_count=len(source.content.splitlines()),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


@router.get("/sources/{source_id}/chunks", response_model=SourceChunkList)
def list_source_chunks(
    source_id: uuid.UUID,
    db: DatabaseSession,
    user_id: CurrentUserId,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SourceChunkList:
    items, total = parsing.list_chunks(
        db, user_id=user_id, source_id=source_id, page=page, page_size=page_size
    )
    return SourceChunkList(
        items=[SourceChunkRead.model_validate(item) for item in items],
        page=page, page_size=page_size, total=total,
    )


@router.get("/sources/{source_id}/code-structure", response_model=JavaStructureRead)
def get_code_structure(
    source_id: uuid.UUID,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> JavaStructureRead:
    source = ingestion.get_source(db, user_id=user_id, source_id=source_id)
    if source.source_type != "java":
        raise AppError(
            status_code=409, code="CODE_STRUCTURE_UNAVAILABLE",
            message="当前资料不是 Java 源文件",
        )
    if source.status != SourceStatus.READY:
        raise AppError(
            status_code=409, code="SOURCE_NOT_PARSED",
            message="请先完成 Java 资料解析",
        )
    related_sources, related_sources_truncated = ingestion.list_ready_java_sources(
        db,
        user_id=user_id,
        project_id=source.project_id,
        repository_id=source.repository_id,
        exclude_source_id=source.id,
        limit=99,
    )
    structure = analyze_java(
        source.content,
        source_id=source.id,
        source_path=source.relative_path or source.original_name,
        related_sources=[
            JavaSourceInput(
                source_id=item.id,
                source_path=item.relative_path or item.original_name,
                content=item.content,
            )
            for item in related_sources
        ],
        related_sources_truncated=related_sources_truncated,
    )
    return JavaStructureRead(
        source_id=source.id,
        symbols=[JavaSymbolRead.model_validate(item) for item in structure.symbols],
        calls=[JavaCallRead.model_validate(item) for item in structure.calls],
        related_types=[
            JavaRelatedTypeRead.model_validate(item) for item in structure.related_types
        ],
        type_relationships=[
            JavaTypeRelationshipRead.model_validate(item)
            for item in structure.type_relationships
        ],
        related_methods=[
            JavaRelatedMethodRead.model_validate(item)
            for item in structure.related_methods
        ],
        cross_file_calls=[
            JavaCrossFileCallRead.model_validate(item)
            for item in structure.cross_file_calls
        ],
        truncated=structure.truncated,
    )

