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
    created_at: datetime
    updated_at: datetime


class RepositoryList(BaseModel):
    items: list[RepositoryRead]
    page: int
    page_size: int
    total: int
