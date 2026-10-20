import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    candidate_id: uuid.UUID
    type: str
    name: str
    summary: str
    confidence: float
    status: str
    valid_from: datetime
    valid_to: datetime | None
    evidence_count: int = 0


class KnowledgeEdgeRead(KnowledgeNodeRead):
    source_id: uuid.UUID
    target_id: uuid.UUID


class GraphRead(BaseModel):
    nodes: list[KnowledgeNodeRead]
    edges: list[KnowledgeEdgeRead]
    truncated: bool


class FormalEvidenceRead(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    chunk_id: uuid.UUID
    title: str
    uri: str
    git_url: str | None = None
    quote: str
    start_line: int
    end_line: int
    heading_path: list[str]


class EntityDetail(BaseModel):
    entity: KnowledgeNodeRead
    evidence: list[FormalEvidenceRead]
    relationships: list[KnowledgeEdgeRead]
    truncated: bool


class RelationshipDetail(BaseModel):
    relationship: KnowledgeEdgeRead
    evidence: list[FormalEvidenceRead]
