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
    source_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    status: Literal["imported", "reused", "skipped"]
    error_code: str | None = None


class GithubRepositorySyncResult(BaseModel):
    repository_id: uuid.UUID
    ref: str
    commit_sha: str
    imported_count: int
    reused_count: int
    skipped_count: int
    truncated: bool
    items: list[GithubRepositorySyncItem]


class RepositoryList(BaseModel):
    items: list[RepositoryRead]
    page: int
    page_size: int
    total: int
