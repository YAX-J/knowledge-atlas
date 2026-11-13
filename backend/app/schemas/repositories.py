import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RepositoryResolve(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    kind: Literal["local_folder"] = "local_folder"

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if (
            value in {".", ".."}
            or any(character in value for character in "/\\\x00\r\n")
        ):
            raise ValueError("repository name must be one folder name")
        return value


class RepositoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    kind: str
    provider: str | None
    remote_owner: str | None
    remote_name: str | None
    remote_url: str | None
    provider_repository_id: str | None
    created_at: datetime
    updated_at: datetime


class GithubRepositoryResolve(BaseModel):
    remote_url: str = Field(min_length=1, max_length=1024)
    local_repository_id: uuid.UUID | None = None

    @field_validator("remote_url", mode="before")
    @classmethod
    def normalize_remote_url(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class GithubRepositorySync(BaseModel):
    ref: str | None = Field(default=None, max_length=255)
    rescan: bool = False
    continue_from_snapshot: uuid.UUID | None = None
    resume_incomplete: bool = False

    @field_validator("ref", mode="before")
    @classmethod
    def normalize_ref(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("ref")
    @classmethod
    def validate_ref(cls, value: str | None) -> str | None:
        if value is not None and any(character in value for character in "\x00\r\n"):
            raise ValueError("Git ref contains an invalid control character")
        return value


class GithubRepositorySyncItem(BaseModel):
    path: str
    previous_path: str | None = None
    source_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    status: Literal[
        "imported", "reused", "unchanged", "renamed", "deleted", "skipped"
    ]
    error_code: str | None = None


class GithubRepositorySyncResult(BaseModel):
    repository_id: uuid.UUID
    snapshot_id: uuid.UUID
    ref: str
    commit_sha: str
    commit_url: str | None
    imported_count: int
    reused_count: int
    unchanged_count: int
    renamed_count: int
    deleted_count: int
    skipped_count: int
    truncated: bool
    deletion_detection_complete: bool
    items: list[GithubRepositorySyncItem]
    continuation_snapshot_id: uuid.UUID | None = None
    total_supported_files: int | None = None
    completed_files: int | None = None
    remaining_files: int | None = None
    access: Literal['public', 'private', 'unknown'] = 'unknown'
    pending_directories: int = 0
    tree_complete: bool = True
    traversal_blocked: bool = False


class GithubWorkItemImport(BaseModel):
    state: Literal["all", "open", "closed"] = "all"
    item_type: Literal["all", "issue", "pull_request"] = "all"
    include_comments: bool = True
    include_reviews: bool = True
    include_review_threads: bool = True
    limit: int = Field(default=20, ge=1, le=20)


class GithubWorkItemImportItem(BaseModel):
    number: int
    item_type: Literal["issue", "pull_request"]
    title: str
    html_url: str
    source_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    status: Literal["imported", "reused", "skipped"]
    comments_truncated: bool = False
    review_source_id: uuid.UUID | None = None
    review_task_id: uuid.UUID | None = None
    review_status: Literal["imported", "reused", "skipped", "not_requested"] = (
        "not_requested"
    )
    reviews_count: int = 0
    review_comments_count: int = 0
    reviews_truncated: bool = False
    review_comments_truncated: bool = False
    review_threads_status: Literal[
        "included", "token_required", "not_requested"
    ] = "not_requested"
    review_threads_count: int = 0
    resolved_review_threads_count: int = 0
    review_threads_truncated: bool = False
    error_code: str | None = None
    review_error_code: str | None = None


class GithubWorkItemImportResult(BaseModel):
    repository_id: uuid.UUID
    imported_count: int
    reused_count: int
    skipped_count: int
    review_imported_count: int
    review_reused_count: int
    review_skipped_count: int
    truncated: bool
    items: list[GithubWorkItemImportItem]


class RepositorySnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    ref: str
    commit_sha: str
    tree_sha: str
    commit_url: str | None
    commit_message: str
    commit_source_id: uuid.UUID | None = None
    commit_task_id: uuid.UUID | None = None
    committed_at: datetime | None
    truncated: bool
    deletion_detection_complete: bool
    file_count: int
    imported_count: int
    reused_count: int
    unchanged_count: int
    renamed_count: int
    deleted_count: int
    skipped_count: int
    downloaded_bytes: int
    created_at: datetime


class RepositorySnapshotList(BaseModel):
    items: list[RepositorySnapshotRead]
    page: int
    page_size: int
    total: int


class SnapshotCommitSourceRead(BaseModel):
    snapshot_id: uuid.UUID
    source_id: uuid.UUID
    task_id: uuid.UUID
    status: str
    reused: bool
    git_url: str


class RepositorySnapshotFileRead(BaseModel):
    id: uuid.UUID
    path: str
    previous_path: str | None
    blob_sha: str
    size_bytes: int
    status: Literal["imported", "reused", "unchanged", "renamed", "deleted", "skipped"]
    error_code: str | None
    source_id: uuid.UUID | None
    task_id: uuid.UUID | None
    source_status: str | None
    git_url: str | None


class RepositorySnapshotFileList(BaseModel):
    snapshot_id: uuid.UUID
    repository_id: uuid.UUID
    commit_sha: str
    truncated: bool
    deletion_detection_complete: bool
    items: list[RepositorySnapshotFileRead]
    page: int
    page_size: int
    total: int


class RepositoryList(BaseModel):
    items: list[RepositoryRead]
    page: int
    page_size: int
    total: int
