import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.domain import SourceStatus


class SourceUploadResponse(BaseModel):
    source_id: uuid.UUID
    task_id: uuid.UUID
    status: str


class SourceRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    original_name: str
    media_type: str
    source_type: str
    size_bytes: int
    content_sha256: str
    status: SourceStatus
    content_preview: str
    line_count: int
    created_at: datetime
    updated_at: datetime

