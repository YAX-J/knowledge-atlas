import math
import uuid
from datetime import datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.domain import SourceChunk, SourceDocument, utc_now
from app.models.graph import KnowledgeEmbedding, KnowledgeEntity, KnowledgeEvidence
from app.schemas.search import SearchHit, SearchRead
from app.services import embeddings as embedding_service
from app.services import graph
from app.services.projects import get_project


def _base_conditions(
    user_id: uuid.UUID, project_id: uuid.UUID, valid_at: datetime | None, types: list[str],
):
    conditions = list(graph.visible(KnowledgeEntity, user_id, project_id, valid_at or utc_now()))
    if types:
        conditions.append(KnowledgeEntity.type.in_(types))
    return conditions


def _keyword_search(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, query: str,
    types: list[str], valid_at: datetime | None, top_k: int,
) -> SearchRead:
    words = query.split()
    if not words or len(words) > 8:
        raise AppError(status_code=422, code='SEARCH_QUERY_INVALID', message='请输入 1–8 个关键词，以空格分隔')
    terms = list(dict.fromkeys(word.lower() for word in words))
    normalized = ' '.join(query.split())
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
    term_conditions = []
    score = case((func.lower(KnowledgeEntity.name) == normalized.lower(), 50), else_=0)
    for term in terms:
        matches = {
            'name': KnowledgeEntity.name.icontains(term, autoescape=True),
            'summary': KnowledgeEntity.summary.icontains(term, autoescape=True),
            'evidence': evidence.where(KnowledgeEvidence.quote.icontains(term, autoescape=True)).exists(),
        }
        term_conditions.append(or_(*matches.values()))
        for field, weight in [('name', 10), ('summary', 3), ('evidence', 1)]:
            field_matches[field].append(matches[field])
            score = score + case((matches[field], weight), else_=0)
    flags = [or_(*matches).label(field) for field, matches in field_matches.items()]
    statement = select(KnowledgeEntity, score.label('keyword_score'), *flags).where(
        *_base_conditions(user_id, project_id, valid_at, types), *term_conditions,
    )
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
    return SearchRead(query=normalized, mode='keyword', items=items, truncated=truncated)


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _vector_search(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, query: str,
    types: list[str], valid_at: datetime | None, top_k: int, settings: Settings,
) -> SearchRead:
    normalized = ' '.join(query.split())
    if not normalized:
        raise AppError(status_code=422, code='SEARCH_QUERY_INVALID', message='请输入要检索的问题或描述')
    try:
        query_vector = embedding_service.embed_texts(settings, [normalized])[0]
    except embedding_service.EmbeddingError as exc:
        raise AppError(status_code=503, code=exc.code, message=exc.message) from exc

    conditions = _base_conditions(user_id, project_id, valid_at, types)
    eligible_count = db.scalar(select(func.count()).select_from(KnowledgeEntity).where(*conditions)) or 0
    joined = select(KnowledgeEntity, KnowledgeEmbedding).join(
        KnowledgeEmbedding, KnowledgeEmbedding.entity_id == KnowledgeEntity.id,
    ).where(
        *conditions,
        KnowledgeEmbedding.user_id == user_id,
        KnowledgeEmbedding.project_id == project_id,
        KnowledgeEmbedding.model == settings.embedding_model,
        KnowledgeEmbedding.dimensions == settings.embedding_dimensions,
    )
    indexed_count = db.scalar(select(func.count()).select_from(joined.subquery())) or 0
    if db.get_bind().dialect.name == 'postgresql':
        distance = KnowledgeEmbedding.embedding.cosine_distance(query_vector)
        rows = db.execute(joined.add_columns(distance.label('distance')).order_by(
            distance, KnowledgeEntity.name, KnowledgeEntity.id,
        ).limit(top_k + 1)).all()
        ranked = [(row[0], max(-1.0, min(1.0, 1.0 - float(row[2])))) for row in rows]
    else:
        candidates = db.execute(joined).all()
        ranked = sorted(
            ((row[0], _cosine(list(row[1].embedding), query_vector)) for row in candidates),
            key=lambda item: (-item[1], item[0].name, str(item[0].id)),
        )[:top_k + 1]
    truncated = len(ranked) > top_k
    ranked = ranked[:top_k]
    reads = graph._reads(db, [item[0] for item in ranked])
    items = [SearchHit(
        entity=read,
        vector_score=round(score, 6),
        matched_fields=[],
        evidence=graph._evidence_read(db, entity)[:3],
    ) for (entity, score), read in zip(ranked, reads, strict=True)]
    return SearchRead(
        query=normalized, mode='vector', items=items, truncated=truncated,
        indexed_count=indexed_count, eligible_count=eligible_count,
    )


def search_knowledge(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, query: str,
    types: list[str], valid_at: datetime | None, top_k: int, mode: str,
    settings: Settings,
) -> SearchRead:
    get_project(db, user_id=user_id, project_id=project_id)
    if mode == 'vector':
        return _vector_search(
            db, user_id=user_id, project_id=project_id, query=query, types=types,
            valid_at=valid_at, top_k=top_k, settings=settings,
        )
    return _keyword_search(
        db, user_id=user_id, project_id=project_id, query=query, types=types,
        valid_at=valid_at, top_k=top_k,
    )
