import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.graph import FormalEvidenceRead, KnowledgeNodeRead


class GraphSearchSignal(BaseModel):
    relationship_id: uuid.UUID
    relationship_type: str
    relationship_name: str
    related_entity_id: uuid.UUID
    related_entity_name: str
    score: float


class SearchWeights(BaseModel):
    keyword: float
    vector: float
    graph: float


class SearchHit(BaseModel):
    entity: KnowledgeNodeRead
    keyword_score: int | None = None
    vector_score: float | None = None
    keyword_component: float | None = None
    vector_component: float | None = None
    graph_score: float | None = None
    hybrid_score: float | None = None
    matched_fields: list[Literal['name', 'summary', 'evidence']]
    graph_connections: list[GraphSearchSignal] = Field(default_factory=list)
    evidence: list[FormalEvidenceRead]


class SearchRead(BaseModel):
    query: str
    mode: Literal['keyword', 'vector', 'hybrid'] = 'keyword'
    items: list[SearchHit]
    truncated: bool
    indexed_count: int | None = None
    eligible_count: int | None = None
    weights: SearchWeights | None = None


class EmbeddingRebuildRead(BaseModel):
    model: str
    dimensions: int
    eligible_count: int
    updated_count: int
    reused_count: int
