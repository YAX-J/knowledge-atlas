import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.domain import ReviewStatus
from app.schemas.tasks import TaskRead


EntityType = Literal[
    "Project", "CodeFile", "CodeEntity", "Technology", "Concept", "Problem",
    "Solution", "Decision", "Alternative", "Constraint",
]
RelationType = Literal[
    "BELONGS_TO", "CONTAINS", "DEPENDS_ON", "CALLS", "USES", "SOLVES",
    "CAUSED_BY", "AFFECTS", "DECIDED_IN", "CHOSEN_OVER", "CONSTRAINED_BY",
    "IMPLEMENTED_BY", "EVIDENCED_BY", "EXTRACTED_FROM", "LEARNED_FROM", "SUPERSEDES",
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Summary = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
LocalId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class EvidenceDraft(StrictModel):
    chunk_id: uuid.UUID
    quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class CandidateDraft(StrictModel):
    local_id: LocalId
    summary: Summary
    confidence: float = Field(ge=0, le=1, strict=True)
    evidence: list[EvidenceDraft] = Field(min_length=1, max_length=5)


class EntityDraft(CandidateDraft):
    type: EntityType
    name: Name


class RelationDraft(CandidateDraft):
    type: RelationType
    source: LocalId
    target: LocalId


class ExtractionDraft(StrictModel):
    entities: list[EntityDraft] = Field(max_length=50)
    relations: list[RelationDraft] = Field(max_length=100)

    @model_validator(mode="after")
    def validate_references(self):
        ids = [item.local_id for item in [*self.entities, *self.relations]]
        if len(ids) != len(set(ids)):
            raise ValueError("Candidate local IDs must be unique")
        entity_ids = {item.local_id for item in self.entities}
        if any(item.source not in entity_ids or item.target not in entity_ids for item in self.relations):
            raise ValueError("Relationship endpoints must reference extracted entities")
        return self


class EvidenceRead(BaseModel):
    chunk_id: uuid.UUID
    quote: str
    start_line: int
    end_line: int
    heading_path: list[str]


class ReviewRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    source_id: uuid.UUID
    task_id: uuid.UUID
    kind: Literal["entity", "relation"]
    type: str
    name: str
    summary: str
    confidence: float
    review_status: ReviewStatus
    knowledge_id: uuid.UUID | None = None
    evidence: list[EvidenceRead]
    source_candidate_id: uuid.UUID | None = None
    target_candidate_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class ReviewList(BaseModel):
    items: list[ReviewRead]
    page: int
    page_size: int
    total: int


class ReviewChanges(StrictModel):
    name: Name | None = None
    summary: Summary | None = None


class ReviewResolve(StrictModel):
    action: Literal["confirm", "reject"]
    changes: ReviewChanges = Field(default_factory=ReviewChanges)

    @model_validator(mode="after")
    def reject_has_no_changes(self):
        if self.action == "reject" and self.changes.model_dump(exclude_none=True):
            raise ValueError("Rejection cannot modify the candidate")
        return self


class ExtractionRead(BaseModel):
    task: TaskRead | None
    candidate_count: int
    review_counts: dict[Literal['pending', 'confirmed', 'rejected'], int] = Field(
        default_factory=lambda: {'pending': 0, 'confirmed': 0, 'rejected': 0})
