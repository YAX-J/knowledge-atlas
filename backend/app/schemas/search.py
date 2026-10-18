from typing import Literal

from pydantic import BaseModel

from app.schemas.graph import FormalEvidenceRead, KnowledgeNodeRead


class SearchHit(BaseModel):
    entity: KnowledgeNodeRead
    keyword_score: int | None = None
    vector_score: float | None = None
    matched_fields: list[Literal['name', 'summary', 'evidence']]
    evidence: list[FormalEvidenceRead]


class SearchRead(BaseModel):
    query: str
    mode: Literal['keyword', 'vector'] = 'keyword'
    items: list[SearchHit]
    truncated: bool
    indexed_count: int | None = None
    eligible_count: int | None = None


class EmbeddingRebuildRead(BaseModel):
    model: str
    dimensions: int
    eligible_count: int
    updated_count: int
    reused_count: int
