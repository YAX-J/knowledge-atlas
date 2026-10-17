from typing import Literal

from pydantic import BaseModel

from app.schemas.graph import FormalEvidenceRead, KnowledgeNodeRead


class SearchHit(BaseModel):
    entity: KnowledgeNodeRead
    keyword_score: int
    matched_fields: list[Literal['name', 'summary', 'evidence']]
    evidence: list[FormalEvidenceRead]


class SearchRead(BaseModel):
    query: str
    mode: Literal['keyword'] = 'keyword'
    items: list[SearchHit]
    truncated: bool
