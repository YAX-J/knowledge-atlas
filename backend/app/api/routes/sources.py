import uuid

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.core.config import get_settings
from app.schemas.sources import SourceRead, SourceUploadResponse
from app.services import ingestion


router = APIRouter(tags=["sources"])


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
) -> SourceUploadResponse:
    source, task = await ingestion.create_source_and_task(
        db,
        settings=get_settings(),
        user_id=user_id,
        project_id=project_id,
        upload=file,
        source_type=source_type,
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
    return SourceRead(
        id=source.id,
        project_id=source.project_id,
        original_name=source.original_name,
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

