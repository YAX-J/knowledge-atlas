import uuid
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.graph import FormalEvidenceRead


QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
AnswerText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
MissingText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class QuestionCreate(StrictModel):
    question: QuestionText
    valid_at: AwareDatetime | None = None
    retrieval_mode: Literal['hybrid', 'rrf', 'vector', 'bm25'] = 'hybrid'


class AnswerDraft(StrictModel):
    supported: bool
    answer: AnswerText
    confidence: float = Field(ge=0, le=1, strict=True)
    citation_ids: list[uuid.UUID] = Field(max_length=5)
    missing_information: list[MissingText] = Field(max_length=5)

    @model_validator(mode='after')
    def validate_support(self):
        if self.supported and not self.citation_ids:
            raise ValueError('Supported answers require at least one citation')
        if not self.supported and not self.missing_information:
            raise ValueError('Unsupported answers must identify missing information')
        if len(self.citation_ids) != len(set(self.citation_ids)):
            raise ValueError('Citation IDs must be unique')
        return self


class EvidenceEntityRead(BaseModel):
    id: uuid.UUID
    name: str


class QuestionEvidenceRead(FormalEvidenceRead):
    entity_id: uuid.UUID
    entity_name: str
    related_entities: list[EvidenceEntityRead] = Field(default_factory=list)


class RetrievalSummary(BaseModel):
    keyword_hits: int
    vector_hits: int
    graph_hits: int
    indexed_count: int
    eligible_count: int
    mode: Literal['hybrid', 'rrf', 'vector', 'bm25'] = 'hybrid'
    bm25_hits: int = 0
    unique_evidence_count: int = 0
    duplicate_evidence_count: int = 0
    truncated: bool = False


class QuestionRead(BaseModel):
    id: uuid.UUID
    question: str
    supported: bool
    answer: str
    confidence: float
    entity_ids: list[uuid.UUID]
    evidence: list[QuestionEvidenceRead]
    retrieval: RetrievalSummary
    missing_information: list[str]
