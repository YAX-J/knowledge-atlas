import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.schemas.graph import FormalEvidenceRead, KnowledgeNodeRead

ChangeKind = Literal["SUPERSEDES", "SUPPLEMENTS", "CONFLICTS_WITH"]


class ChangeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_entity_id: uuid.UUID
    old_entity_id: uuid.UUID
    evidence_id: uuid.UUID
    kind: ChangeKind
    reason: str = Field(min_length=1, max_length=2000)
    effective_at: AwareDatetime

    @field_validator("reason")
    @classmethod
    def nonempty(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("A review reason is required")
        return value


class ChangeResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["confirm", "reject"]


class ChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    new_entity_id: uuid.UUID
    old_entity_id: uuid.UUID
    evidence_id: uuid.UUID
    new_entity_name: str
    old_entity_name: str
    kind: ChangeKind
    reason: str
    effective_at: datetime
    review_status: Literal["pending", "confirmed", "rejected"]
    resolved_at: datetime | None
    created_at: datetime
    before: dict
    after: dict
    evidence: list[FormalEvidenceRead]

    @field_validator("effective_at", "resolved_at", "created_at")
    @classmethod
    def utc_timestamp(cls, value):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class ChangeList(BaseModel):
    items: list[ChangeRead]
    total: int
    page: int
    page_size: int


class EvolutionRead(BaseModel):
    entities: list[KnowledgeNodeRead]
    changes: list[ChangeRead]
    truncated: bool


class GovernanceFinding(BaseModel):
    id: uuid.UUID
    kind: Literal["missing_evidence", "duplicate", "possible_conflict", "orphan"]
    entity_ids: list[uuid.UUID]
    message: str


class GovernanceRead(BaseModel):
    checked_at: datetime
    scanned_entity_count: int
    truncated: bool
    findings: list[GovernanceFinding]
