import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ArchiveRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    archived: bool = Field(strict=True)
    reason: Reason


class SourceArchiveRead(BaseModel):
    source_id: uuid.UUID
    archived: bool


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: uuid.UUID
    claim_index: int = Field(ge=0, le=7, strict=True)
    category: Literal['incorrect','irrelevant_citation','overstatement','wrong_version','incomplete']
    comment: Reason


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    turn_id: uuid.UUID
    answer_sha256: str
    claim_index: int
    claim_text: str
    category: str
    comment: str
    created_at: datetime
