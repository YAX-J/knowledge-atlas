import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, AwareDatetime, field_validator
from typing import Annotated, Literal
from app.schemas.questions import QuestionRead, QuestionText

Mode = Literal['hybrid', 'rrf', 'vector', 'bm25', 'bm25_source']


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] = '新的证据会话'


class TimestampRead(BaseModel):
    @field_validator('created_at', 'updated_at', 'valid_at', check_fields=False)
    @classmethod
    def utc_time(cls, value):
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


class ConversationRead(TimestampRead):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationList(BaseModel):
    items: list[ConversationRead]
    total: int
    page: int
    page_size: int


class TurnCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: uuid.UUID
    question: QuestionText
    retrieval_mode: Mode = 'rrf'
    valid_at: AwareDatetime | None = None
    retry_interrupted: bool = False


class TurnRead(TimestampRead):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    request_id: uuid.UUID
    position: int
    question: str
    retrieval_mode: Mode
    valid_at: datetime | None
    status: Literal['running', 'succeeded', 'failed', 'interrupted']
    error_code: str | None
    answer: QuestionRead | None
    created_at: datetime


class TurnList(BaseModel):
    items: list[TurnRead]
    total: int
    page: int
    page_size: int
