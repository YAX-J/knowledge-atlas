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
    retrieval_mode: Literal['hybrid', 'rrf', 'vector', 'bm25', 'bm25_source'] = 'rrf'


class AnswerDraft(StrictModel):
    """Legacy flat draft retained for historical diagnostic adapters, not provider parsing."""
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


class AnswerClaim(StrictModel):
    text: MissingText
    status: Literal['supported', 'insufficient']
    citation_ids: list[uuid.UUID] = Field(max_length=5)

    @model_validator(mode='after')
    def validate_citations(self):
        if (self.status == 'supported') != bool(self.citation_ids):
            raise ValueError('Supported claims require citations; insufficient claims cannot cite')
        if len(self.citation_ids) != len(set(self.citation_ids)):
            raise ValueError('Claim citation IDs must be unique')
        return self


class _ClaimAnswerFields(StrictModel):
    confidence: float = Field(ge=0, le=1, strict=True)
    claims: list[AnswerClaim] = Field(min_length=1, max_length=8)
    missing_information: list[MissingText] = Field(max_length=5)

    @property
    def citation_ids(self) -> list[uuid.UUID]:
        return list(dict.fromkeys(item_id for claim in self.claims for item_id in claim.citation_ids))

    @property
    def answer(self) -> str:
        return '\n\n'.join(claim.text for claim in self.claims)

    @model_validator(mode='after')
    def validate_support(self):
        if any(claim.status == 'insufficient' for claim in self.claims) and not self.missing_information:
            raise ValueError('Insufficient claims must identify missing information')
        if len(self.citation_ids) > 5 or len(self.answer) > 4000:
            raise ValueError('Answer exceeds citation or text budget')
        return self


class ClaimAnswerDraft(_ClaimAnswerFields):
    """Current v3 provider output; aggregate support belongs to the backend."""

    @property
    def supported(self) -> bool:
        return all(claim.status == 'supported' for claim in self.claims)


class ClaimAnswerDraftV2(_ClaimAnswerFields):
    """Strict historical v2 diagnostic adapter, never a provider fallback."""

    supported: bool

    @model_validator(mode='after')
    def validate_overall_support(self):
        if self.supported != all(claim.status == 'supported' for claim in self.claims):
            raise ValueError('Overall support must agree with claim support')
        return self


class EvidenceEntityRead(BaseModel):
    id: uuid.UUID
    name: str


class EvidenceRelationshipRead(BaseModel):
    id: uuid.UUID
    type: str
    source: EvidenceEntityRead
    target: EvidenceEntityRead
    valid_at: AwareDatetime
    valid_from: AwareDatetime
    valid_to: AwareDatetime | None


class QuestionEvidenceRead(FormalEvidenceRead):
    entity_id: uuid.UUID
    entity_name: str
    related_entities: list[EvidenceEntityRead] = Field(default_factory=list)
    relationship: EvidenceRelationshipRead | None = None


class RetrievalSummary(BaseModel):
    keyword_hits: int
    vector_hits: int
    graph_hits: int
    indexed_count: int
    eligible_count: int
    mode: Literal['hybrid', 'rrf', 'vector', 'bm25', 'bm25_source'] = 'hybrid'
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
    answer_protocol: Literal['evidence-claims-v2', 'evidence-claims-v3'] | None = None
    claims: list[AnswerClaim] | None = None
