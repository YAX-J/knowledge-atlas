import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.names import normalize_name as normalized


class OperationCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: uuid.UUID
    action: Literal['alias', 'merge', 'unmerge', 'withdraw', 'reactivate', 'reverse_change']
    kind: Literal['entity', 'relationship'] = 'entity'
    knowledge_id: uuid.UUID
    target_id: uuid.UUID | None = None
    alias: str | None = Field(default=None, max_length=255)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator('reason', 'alias')
    @classmethod
    def nonempty(cls, value):
        if value is not None:
            value = value.strip()
            if not value or '\x00' in value:
                raise ValueError('Text must not be blank')
        return value

    @field_validator('alias')
    @classmethod
    def normalized_alias_length(cls, value):
        if value is not None and len(normalized(value)) > 255:
            raise ValueError('Normalized alias must contain at most 255 characters')
        return value


class OperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    action: str
    reason: str
    payload: dict
    before: dict
    after: dict
    created_at: datetime

    @field_validator('created_at')
    @classmethod
    def utc_time(cls, value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class OperationList(BaseModel):
    items: list[OperationRead]
    total: int
    page: int
    page_size: int


class IdentityRead(BaseModel):
    entity_id: uuid.UUID
    canonical_id: uuid.UUID
    aliases: list[str]
    member_ids: list[uuid.UUID]


class EvolutionGroupCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: uuid.UUID
    old_entity_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)
    new_entity_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator('reason')
    @classmethod
    def nonempty(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('A reason is required')
        return value
