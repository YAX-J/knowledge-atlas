import uuid
from datetime import datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.domain import SourceChunk, SourceDocument, utc_now
from app.models.graph import KnowledgeEntity, KnowledgeEvidence
from app.schemas.search import SearchHit, SearchRead
from app.services import graph
from app.services.projects import get_project


def search_knowledge(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, query: str,
    types: list[str], valid_at: datetime | None, top_k: int,
) -> SearchRead:
    get_project(db, user_id=user_id, project_id=project_id)
    words = query.split()
    if not words or len(words) > 8:
        raise AppError(status_code=422, code='SEARCH_QUERY_INVALID', message='请输入 1–8 个关键词，以空格分隔')
    terms = list(dict.fromkeys(word.lower() for word in words))
    normalized = ' '.join(query.split())
    # Correlated EXISTS keeps multiple matching quotes from duplicating a hit.
    evidence = select(KnowledgeEvidence.id).join(
        SourceDocument, SourceDocument.id == KnowledgeEvidence.source_id,
    ).join(SourceChunk, SourceChunk.id == KnowledgeEvidence.chunk_id).where(
        KnowledgeEvidence.entity_id == KnowledgeEntity.id,
        KnowledgeEvidence.user_id == user_id, KnowledgeEvidence.project_id == project_id,
        SourceDocument.user_id == user_id, SourceDocument.project_id == project_id,
        SourceChunk.user_id == user_id, SourceChunk.project_id == project_id,
        SourceChunk.source_id == KnowledgeEvidence.source_id,
    )
    field_matches = {'name': [], 'summary': [], 'evidence': []}
    conditions = []
    score = case((func.lower(KnowledgeEntity.name) == normalized.lower(), 50), else_=0)
    for term in terms:
        matches = {
            'name': KnowledgeEntity.name.icontains(term, autoescape=True),
            'summary': KnowledgeEntity.summary.icontains(term, autoescape=True),
            'evidence': evidence.where(KnowledgeEvidence.quote.icontains(term, autoescape=True)).exists(),
        }
        conditions.append(or_(*matches.values()))
        for field, weight in [('name', 10), ('summary', 3), ('evidence', 1)]:
            field_matches[field].append(matches[field])
            score = score + case((matches[field], weight), else_=0)
    flags = [or_(*matches).label(field) for field, matches in field_matches.items()]
    statement = select(KnowledgeEntity, score.label('keyword_score'), *flags).where(
        *graph.visible(KnowledgeEntity, user_id, project_id, valid_at or utc_now()), *conditions,
    )
    if types:
        statement = statement.where(KnowledgeEntity.type.in_(types))
    rows = db.execute(statement.order_by(score.desc(), KnowledgeEntity.name, KnowledgeEntity.id).limit(top_k + 1)).all()
    truncated = len(rows) > top_k
    rows = rows[:top_k]
    entities = graph._reads(db, [row[0] for row in rows])
    items = []
    for row, entity in zip(rows, entities, strict=True):
        quotes = graph._evidence_read(db, row[0])
        quotes.sort(key=lambda item: not any(term in item.quote.lower() for term in terms))
        items.append(SearchHit(
            entity=entity, keyword_score=row[1],
            matched_fields=[field for field, matched in zip(field_matches, row[2:], strict=True) if matched],
            evidence=quotes[:3],
        ))
    return SearchRead(query=normalized, items=items, truncated=truncated)
