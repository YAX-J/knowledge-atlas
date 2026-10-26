import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RetirementCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: uuid.UUID
    kind: Literal['entity', 'relationship']
    knowledge_id: uuid.UUID
    category: Literal['correction', 'obsolete']
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator('reason')
    @classmethod
    def nonempty(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('A retirement reason is required')
        return value


class RetirementRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    kind: Literal['entity', 'relationship']
    knowledge_id: uuid.UUID
    name: str
    category: Literal['correction', 'obsolete']
    reason: str
    effective_at: datetime
    before: dict
    after: dict


class RetirementList(BaseModel):
    items: list[RetirementRead]
    total: int
    page: int
    page_size: int
