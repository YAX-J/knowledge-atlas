import uuid
from datetime import datetime
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
    bm25_score: float | None = None
    vector_score: float | None = None
    keyword_component: float | None = None
    vector_component: float | None = None
    graph_score: float | None = None
    hybrid_score: float | None = None
    rrf_score: float | None = None
    lexical_rank: int | None = None
    vector_rank: int | None = None
    matched_fields: list[Literal['name', 'summary', 'evidence', 'provenance']]
    graph_connections: list[GraphSearchSignal] = Field(default_factory=list)
    evidence: list[FormalEvidenceRead]


class LexicalSearchInfo(BaseModel):
    protocol: Literal['mixed-bm25-v1', 'mixed-bm25-source-v1', 'mixed-bm25-v2', 'mixed-bm25-source-v2'] = 'mixed-bm25-v2'
    query_terms: list[str]
    scanned_count: int
    entity_limit: int
    text_limit_per_entity: int
    batch_size: int | None = None
    evidence_limit_per_entity: int | None = None
    matched_count: int | None = None
    results_truncated: bool = False
    truncated_reasons: list[Literal['entity_limit', 'evidence_limit', 'text_limit']]


class SearchRead(BaseModel):
    query: str
    mode: Literal['keyword', 'bm25', 'bm25_source', 'vector', 'hybrid', 'rrf'] = 'keyword'
    items: list[SearchHit]
    truncated: bool
    indexed_count: int | None = None
    eligible_count: int | None = None
    weights: SearchWeights | None = None
    lexical: LexicalSearchInfo | None = None
    hybrid_protocol: Literal['bm25-vector-graph-v2'] | None = None


class EmbeddingRebuildRead(BaseModel):
    model: str
    dimensions: int
    eligible_count: int
    updated_count: int
    reused_count: int
    remaining_count: int = 0
    completed_batches: int = 0


class EmbeddingStatusRead(BaseModel):
    model: str
    dimensions: int
    configured: bool
    checked_at: datetime
    eligible_count: int
    indexed_count: int
    missing_count: int
    stale_count: int
    current_count: int
    scanned_count: int
    scan_limit: int
    truncated: bool


class EmbeddingJobRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: Literal['running', 'succeeded', 'failed']
    interrupted: bool
    started_at: datetime
    lease_expires_at: datetime
    completed_at: datetime | None
    result: EmbeddingRebuildRead | None
    error: dict[str, str] | None
