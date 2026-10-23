import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.domain import SourceStatus, TaskStatus


class SourceUploadResponse(BaseModel):
    source_id: uuid.UUID
    task_id: uuid.UUID
    status: TaskStatus


class SourceRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    repository_id: uuid.UUID | None
    repository_name: str | None
    git_url: str | None = None
    original_name: str
    relative_path: str | None
    media_type: str
    source_type: str
    size_bytes: int
    content_sha256: str
    status: SourceStatus
    content_preview: str
    line_count: int
    created_at: datetime
    updated_at: datetime


class SourceChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    source_id: uuid.UUID
    position: int
    kind: str
    heading_path: list[str]
    start_line: int
    end_line: int
    content: str
    content_sha256: str


class SourceChunkList(BaseModel):
    items: list[SourceChunkRead]
    page: int
    page_size: int
    total: int


class JavaSymbolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    name: str
    qualified_name: str
    owner: str | None
    start_line: int
    end_line: int


class JavaCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    caller_id: uuid.UUID
    callee_ids: list[uuid.UUID]
    callee_name: str
    line: int
    resolution: str


class CodeSymbolHit(JavaSymbolRead):
    language: str = "java"
    source_id: uuid.UUID
    source_path: str
    repository_id: uuid.UUID | None
    repository_name: str | None
    task_id: uuid.UUID | None
    chunk_id: uuid.UUID | None = None
    chunk_position: int | None = None
    git_url: str | None = None


class CodeSymbolSearchResult(BaseModel):
    query: str
    items: list[CodeSymbolHit]
    scanned_source_count: int
    matched_count: int
    truncated: bool
    has_syntax_errors: bool = False


class JavaRelatedTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    source_path: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int


class JavaTypeRelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_symbol_id: uuid.UUID
    target_ids: list[uuid.UUID]
    target_name: str
    kind: str
    line: int
    resolution: str


class JavaRelatedMethodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    source_path: str
    owner_qualified_name: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int


class JavaCrossFileCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    caller_id: uuid.UUID
    target_ids: list[uuid.UUID]
    receiver: str
    callee_name: str
    line: int
    resolution: str


class JavaStructureRead(BaseModel):
    source_id: uuid.UUID
    language: str = "java"
    has_syntax_errors: bool = False
    symbols: list[JavaSymbolRead]
    calls: list[JavaCallRead]
    related_types: list[JavaRelatedTypeRead]
    type_relationships: list[JavaTypeRelationshipRead]
    related_methods: list[JavaRelatedMethodRead]
    cross_file_calls: list[JavaCrossFileCallRead]
    truncated: bool


class SourceListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    repository_id: uuid.UUID | None
    repository_name: str | None = None
    git_url: str | None = None
    original_name: str
    relative_path: str | None
    source_type: str
    size_bytes: int
    status: SourceStatus
    created_at: datetime
    updated_at: datetime
    task_id: uuid.UUID | None = None
    task_status: TaskStatus | None = None


class SourceList(BaseModel):
    items: list[SourceListItem]
    page: int
    page_size: int
    total: int

