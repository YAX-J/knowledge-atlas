"""Opt-in rank fusion over batched BM25; keyword and hybrid stay unchanged."""
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.domain import utc_now
from app.schemas.search import SearchHit, SearchRead
from app.services import graph, lexical
from app.services.search import _bm25_search, _vector_ranked

RRF_POOL_LIMIT = 100
RRF_CONSTANT = 60


def reciprocal_rank_search(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, query: str,
    types: list[str], valid_at: datetime | None, top_k: int, settings: Settings,
) -> SearchRead:
    at = valid_at or utc_now()
    local = _bm25_search(db, user_id=user_id, project_id=project_id, query=query,
                         types=types, valid_at=at, top_k=RRF_POOL_LIMIT)
    _, vectors, indexed, eligible = _vector_ranked(
        db, user_id=user_id, project_id=project_id, query=local.query, types=types,
        at=at, limit=RRF_POOL_LIMIT + 1, settings=settings,
    )
    truncated = local.truncated or len(vectors) > RRF_POOL_LIMIT
    hits = {hit.entity.id: hit for hit in local.items}
    scores = {}
    for rank, hit in enumerate(local.items, 1):
        hit.lexical_rank = rank
        scores[hit.entity.id] = 1 / (RRF_CONSTANT + rank)
    terms = set(local.lexical.query_terms)
    missing = [entity for entity, _ in vectors[:RRF_POOL_LIMIT] if entity.id not in hits]
    reads = {entity.id: entity for entity in graph._reads(db, missing, at=at)}
    evidence_by_entity = graph.evidence_for_records(db, missing, at=at)
    for rank, (entity, similarity) in enumerate(vectors[:RRF_POOL_LIMIT], 1):
        if entity.id not in hits:
            evidence = evidence_by_entity[entity.id]
            evidence.sort(key=lambda item: (-len(set(lexical.tokenize(item.quote)) & terms),
                                            item.start_line, str(item.id)))
            hits[entity.id] = SearchHit(entity=reads[entity.id], matched_fields=[], evidence=evidence[:3])
        hit = hits[entity.id]
        hit.vector_score = round(similarity, 6)
        hit.vector_rank = rank
        scores[entity.id] = scores.get(entity.id, 0) + 1 / (RRF_CONSTANT + rank)
    ordered = sorted(hits.values(), key=lambda hit: (-scores[hit.entity.id], hit.entity.name, str(hit.entity.id)))
    truncated |= len(ordered) > top_k
    for hit in ordered:
        hit.rrf_score = round(scores[hit.entity.id], 8)
    return SearchRead(query=local.query, mode='rrf', items=ordered[:top_k], truncated=truncated,
                      indexed_count=indexed, eligible_count=eligible, lexical=local.lexical)
