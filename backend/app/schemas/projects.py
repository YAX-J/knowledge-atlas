import uuid
from datetime import datetime, timezone

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("project name must not be blank")
        return value


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None

    @field_validator('created_at', 'updated_at', 'archived_at')
    @classmethod
    def utc_time(cls, value):
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


class ProjectEdit(ProjectCreate):
    model_config = ConfigDict(extra='forbid')
    expected_updated_at: AwareDatetime


class ProjectArchive(BaseModel):
    model_config = ConfigDict(extra='forbid')
    archived: bool = Field(strict=True)
    expected_updated_at: AwareDatetime


class ProjectList(BaseModel):
    items: list[ProjectRead]
    page: int
    page_size: int
    total: int

