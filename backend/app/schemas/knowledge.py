import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.domain import ReviewStatus
from app.schemas.graph import FormalEvidenceRead, KnowledgeEdgeRead
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


TemporalExpression = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class TemporalDraft(StrictModel):
    start: TemporalExpression
    end: TemporalExpression | None = None


class FactValidity(StrictModel):
    valid_from: AwareDatetime
    valid_to: AwareDatetime | None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("The validity end must be later than the start")
        return self


class CandidateDraft(StrictModel):
    local_id: LocalId
    summary: Summary
    confidence: float = Field(ge=0, le=1, strict=True)
    evidence: list[EvidenceDraft] = Field(min_length=1, max_length=5)
    temporal: TemporalDraft | None = None


class EntityDraft(CandidateDraft):
    type: EntityType
    name: Name


class RelationDraft(CandidateDraft):
    type: RelationType
    source: LocalId
    target: LocalId
    fact_slot: Literal["primary_database"] | None = None


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


class ExtractionPlan(BaseModel):
    protocol: str
    plan_sha256: str
    batch_count: int
    max_batches: int
    chunk_count: int
    fragment_count: int
    input_chars: list[int]
    input_limit: int
    model: str
    cached: bool


class ReviewEndpointRead(BaseModel):
    id: uuid.UUID
    name: str
    review_status: ReviewStatus


class RelationshipReplacementApproval(StrictModel):
    old_relationship_id: uuid.UUID
    token: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class RelationshipReplacementRead(BaseModel):
    approval: RelationshipReplacementApproval
    old_relationship: KnowledgeEdgeRead
    evidence: list[FormalEvidenceRead]
    effective_at: AwareDatetime


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
    temporal: TemporalDraft | None = None
    temporal_reference: AwareDatetime | None = None
    validity: FactValidity | None = None
    replacement: RelationshipReplacementRead | None = None
    replacement_issue: str | None = None
    supersedes_relationship_id: uuid.UUID | None = None
    source_candidate_id: uuid.UUID | None = None
    target_candidate_id: uuid.UUID | None = None
    endpoints: list[ReviewEndpointRead] = Field(default_factory=list)
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
    validity: FactValidity | None = None


class ReviewResolve(StrictModel):
    action: Literal["confirm", "reject"]
    changes: ReviewChanges = Field(default_factory=ReviewChanges)
    replacement: RelationshipReplacementApproval | None = None

    @model_validator(mode="after")
    def reject_has_no_changes(self):
        if self.action == "reject" and (self.replacement or self.changes.model_dump(exclude_none=True)
                                         or "validity" in self.changes.model_fields_set):
            raise ValueError("Rejection cannot modify the candidate")
        return self


class ExtractionRead(BaseModel):
    task: TaskRead | None
    candidate_count: int
    review_counts: dict[Literal['pending', 'confirmed', 'rejected'], int] = Field(
        default_factory=lambda: {'pending': 0, 'confirmed': 0, 'rejected': 0})


class ReviewBatchResolve(StrictModel):
    source_id: uuid.UUID
    review_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    action: Literal['confirm', 'reject']

    @model_validator(mode='after')
    def unique_ids(self):
        if len(set(self.review_ids)) != len(self.review_ids):
            raise ValueError('Candidate IDs must be unique')
        return self


class ReviewBatchRead(BaseModel):
    items: list[ReviewRead]
    processed_count: int
