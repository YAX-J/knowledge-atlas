import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.domain import SourceChunk, SourceDocument, utc_now
from app.models.graph import KnowledgeEmbedding, KnowledgeEntity, KnowledgeEvidence, KnowledgeRelationship
from app.models.workspace import EntityAlias
from app.services import identities
from app.schemas.search import GraphSearchSignal, LexicalSearchInfo, SearchHit, SearchRead, SearchWeights
from app.services import embeddings as embedding_service
from app.services import graph
from app.services import lexical
from app.services.projects import get_project


HYBRID_POOL_LIMIT = 100
HYBRID_EDGE_LIMIT = 500
HYBRID_WEIGHTS = SearchWeights(keyword=0.3, vector=0.4, graph=0.3)
BM25_ENTITY_LIMIT = 1000
BM25_EVIDENCE_LIMIT = 5000
BM25_TEXT_LIMIT = 4000
BM25_QUOTE_LIMIT = 2000


@dataclass
class _HybridCandidate:
    entity: KnowledgeEntity
    keyword_score: int = 0
    vector_score: float | None = None
    matched_fields: list[str] = field(default_factory=list)
    graph_score: float = 0.0
    graph_connections: list[GraphSearchSignal] = field(default_factory=list)


def _base_conditions(
    user_id: uuid.UUID, project_id: uuid.UUID, at: datetime, types: list[str],
):
    conditions = list(graph.visible(KnowledgeEntity, user_id, project_id, at))
    if types:
        conditions.append(KnowledgeEntity.type.in_(types))
    return conditions


def _keyword_ranked(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, query: str,
    types: list[str], at: datetime, limit: int, strict_term_limit: bool = True,
):
    words = query.split()
    if not words or (strict_term_limit and len(words) > 8):
        raise AppError(status_code=422, code='SEARCH_QUERY_INVALID', message='请输入 1–8 个关键词，以空格分隔')
    terms = list(dict.fromkeys(word.lower() for word in words))[:8]
    normalized = ' '.join(query.split())
    evidence = select(KnowledgeEvidence.id).join(
        SourceDocument, SourceDocument.id == KnowledgeEvidence.source_id,
    ).join(SourceChunk, SourceChunk.id == KnowledgeEvidence.chunk_id).where(
        identities.canonical(KnowledgeEvidence.entity_id, user_id, project_id, at) == KnowledgeEntity.id,
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
            'name': or_(KnowledgeEntity.name.icontains(term, autoescape=True), select(EntityAlias.id).where(
                EntityAlias.user_id == user_id, EntityAlias.project_id == project_id, EntityAlias.created_at <= at,
                identities.canonical(EntityAlias.entity_id, user_id, project_id, at) == KnowledgeEntity.id,
                EntityAlias.name.icontains(term, autoescape=True)).correlate(KnowledgeEntity).exists()),
            'summary': KnowledgeEntity.summary.icontains(term, autoescape=True),
            'evidence': evidence.where(KnowledgeEvidence.quote.icontains(term, autoescape=True)).exists(),
        }
        term_conditions.append(or_(*matches.values()))
        for field, weight in [('name', 10), ('summary', 3), ('evidence', 1)]:
            field_matches[field].append(matches[field])
            score = score + case((matches[field], weight), else_=0)
    flags = [or_(*matches).label(field) for field, matches in field_matches.items()]
    statement = select(KnowledgeEntity, score.label('keyword_score'), *flags).where(
        *_base_conditions(user_id, project_id, at, types), *term_conditions,
    )
    rows = db.execute(statement.order_by(score.desc(), KnowledgeEntity.name, KnowledgeEntity.id).limit(limit)).all()
    ranked = [(
        row[0], int(row[1]),
        [field for field, matched in zip(field_matches, row[2:], strict=True) if matched],
    ) for row in rows]
    return normalized, terms, ranked


def _keyword_search(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, query: str,
    types: list[str], valid_at: datetime | None, top_k: int,
) -> SearchRead:
    at = valid_at or utc_now()
    normalized, terms, ranked = _keyword_ranked(
        db, user_id=user_id, project_id=project_id, query=query, types=types,
        at=at, limit=top_k + 1,
    )
    rows = ranked
    truncated = len(rows) > top_k
    rows = rows[:top_k]
    entities = graph._reads(db, [row[0] for row in rows], at=at)
    evidence_by_entity = graph.evidence_for_records(db, [row[0] for row in rows], at=at)
    items = []
    for row, entity in zip(rows, entities, strict=True):
        quotes = evidence_by_entity[row[0].id]
        quotes.sort(key=lambda item: not any(term in item.quote.lower() for term in terms))
        items.append(SearchHit(
            entity=entity, keyword_score=row[1],
            matched_fields=row[2],
            evidence=quotes[:3],
        ))
    return SearchRead(query=normalized, mode='keyword', items=items, truncated=truncated)


def _bm25_search(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, query: str,
    types: list[str], valid_at: datetime | None, top_k: int, provenance: bool = False,
) -> SearchRead:
    normalized = ' '.join(query.split())
    if not lexical.tokenize(normalized):
        raise AppError(status_code=422, code='SEARCH_QUERY_INVALID', message='请输入包含文字或标识符的问题；符号精确匹配请使用关键词模式')
    at = valid_at or utc_now()
    conditions = _base_conditions(user_id, project_id, at, types)
    eligible = db.scalar(select(func.count()).select_from(KnowledgeEntity).where(*conditions)) or 0
    entities = list(db.scalars(select(KnowledgeEntity).where(*conditions).order_by(
        KnowledgeEntity.name, KnowledgeEntity.id,
    ).limit(BM25_ENTITY_LIMIT)))
    reasons = {'entity_limit'} if eligible > len(entities) else set()
    ids = [entity.id for entity in entities]
    aliases = identities.alias_names(db, user_id, project_id, at, ids)
    evidence_owner = identities.canonical(KnowledgeEvidence.entity_id, user_id, project_id, at)
    quotes: dict[uuid.UUID, list[str]] = {}
    locations: dict[uuid.UUID, list[str]] = {}
    if ids:
        rows = db.execute(select(
            evidence_owner,
            func.substr(KnowledgeEvidence.quote, 1, BM25_QUOTE_LIMIT),
            func.length(KnowledgeEvidence.quote),
            SourceDocument.original_name, SourceDocument.relative_path,
            SourceChunk.heading_path,
        ).join(SourceDocument, SourceDocument.id == KnowledgeEvidence.source_id).join(
            SourceChunk, SourceChunk.id == KnowledgeEvidence.chunk_id,
        ).where(
            evidence_owner.in_(ids),
            KnowledgeEvidence.user_id == user_id, KnowledgeEvidence.project_id == project_id,
            SourceDocument.user_id == user_id, SourceDocument.project_id == project_id,
            SourceChunk.user_id == user_id, SourceChunk.project_id == project_id,
            SourceChunk.source_id == KnowledgeEvidence.source_id,
        ).order_by(KnowledgeEvidence.entity_id, KnowledgeEvidence.start_line, KnowledgeEvidence.id).limit(
            BM25_EVIDENCE_LIMIT + 1,
        )).all()
        if len(rows) > BM25_EVIDENCE_LIMIT:
            reasons.add('evidence_limit')
        for owner, quote, length, filename, path, headings in rows[:BM25_EVIDENCE_LIMIT]:
            quotes.setdefault(owner, []).append(quote)
            if provenance:
                heading_text = ' '.join(headings)
                if len(heading_text) > 512:
                    reasons.add('text_limit')
                locations.setdefault(owner, []).append(' '.join(value for value in (filename, path, heading_text[:512]) if value))
            if length > BM25_QUOTE_LIMIT:
                reasons.add('text_limit')
    documents = []
    for entity in entities:
        document = {}
        remaining = BM25_TEXT_LIMIT
        fields = [('name', ' '.join([entity.name, *aliases.get(entity.id, [])])), ('summary', entity.summary)]
        if provenance:
            fields.append(('provenance', '\n'.join(dict.fromkeys(locations.get(entity.id, [])))))
        fields.append(('evidence', '\n'.join(quotes.get(entity.id, []))))
        for key, value in fields:
            document[key] = value[:remaining]
            if len(value) > remaining:
                reasons.add('text_limit')
            remaining = max(0, remaining - len(value))
        documents.append(document)
    terms, scores = lexical.rank_fields(documents, normalized)
    ranked = sorted(((entity, score, fields) for entity, (score, fields) in zip(entities, scores, strict=True) if score > 0),
                    key=lambda item: (-item[1], item[0].name, str(item[0].id)))
    truncated = bool(reasons) or len(ranked) > top_k
    ranked = ranked[:top_k]
    reads = graph._reads(db, [item[0] for item in ranked], at=at)
    evidence_by_entity = graph.evidence_for_records(db, [item[0] for item in ranked], at=at)
    items = []
    for (entity, score, fields), read in zip(ranked, reads, strict=True):
        evidence = evidence_by_entity[entity.id]
        evidence.sort(key=lambda item: (-len(set(lexical.tokenize(item.quote +
            (' ' + item.title + ' ' + ' '.join(item.heading_path) if provenance else ''))) & set(terms)), item.start_line, str(item.id)))
        items.append(SearchHit(entity=read, bm25_score=round(score, 6), matched_fields=fields, evidence=evidence[:3]))
    return SearchRead(query=normalized, mode='bm25_source' if provenance else 'bm25', items=items, truncated=truncated, eligible_count=eligible,
                      lexical=LexicalSearchInfo(protocol='mixed-bm25-source-v1' if provenance else 'mixed-bm25-v1', query_terms=terms, scanned_count=len(entities),
                          entity_limit=BM25_ENTITY_LIMIT, text_limit_per_entity=BM25_TEXT_LIMIT,
                          truncated_reasons=sorted(reasons)))


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _vector_ranked(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, query: str,
    types: list[str], at: datetime, limit: int, settings: Settings,
):
    normalized = ' '.join(query.split())
    if not normalized:
        raise AppError(status_code=422, code='SEARCH_QUERY_INVALID', message='请输入要检索的问题或描述')
    conditions = _base_conditions(user_id, project_id, at, types)
    eligible_count = db.scalar(select(func.count()).select_from(KnowledgeEntity).where(*conditions)) or 0
    joined = select(KnowledgeEntity, KnowledgeEmbedding).join(
        KnowledgeEmbedding, identities.canonical(KnowledgeEmbedding.entity_id, user_id, project_id, at) == KnowledgeEntity.id,
    ).where(
        *conditions,
        KnowledgeEmbedding.user_id == user_id,
        KnowledgeEmbedding.project_id == project_id,
        KnowledgeEmbedding.model == settings.embedding_model,
        KnowledgeEmbedding.dimensions == settings.embedding_dimensions,
    )
    indexed_count = db.scalar(select(func.count()).select_from(joined.with_only_columns(KnowledgeEntity.id).distinct().subquery())) or 0
    try:
        # Preserve configuration errors, but never pay to query an empty index.
        embedding_service._require_configuration(settings)
        if not indexed_count:
            return normalized, [], 0, eligible_count
        query_vector = embedding_service.embed_texts(settings, [normalized])[0]
    except embedding_service.EmbeddingError as exc:
        raise AppError(status_code=503, code=exc.code, message=exc.message) from exc
    if db.get_bind().dialect.name == 'postgresql':
        distance = KnowledgeEmbedding.embedding.cosine_distance(query_vector)
        closest = func.min(distance)
        rows = db.execute(joined.with_only_columns(KnowledgeEntity, closest.label('distance')).group_by(KnowledgeEntity.id).order_by(
            closest, KnowledgeEntity.name, KnowledgeEntity.id,
        ).limit(limit)).all()
        ranked = [(row[0], max(-1.0, min(1.0, 1.0 - float(row[1])))) for row in rows]
    else:
        candidates = db.execute(joined).all()
        grouped = {}
        for entity, embedding in candidates:
            score = _cosine(list(embedding.embedding), query_vector)
            if entity.id not in grouped or score > grouped[entity.id][1]:
                grouped[entity.id] = (entity, score)
        ranked = sorted(
            grouped.values(),
            key=lambda item: (-item[1], item[0].name, str(item[0].id)),
        )[:limit]
    return normalized, ranked, indexed_count, eligible_count


def _vector_search(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, query: str,
    types: list[str], valid_at: datetime | None, top_k: int, settings: Settings,
) -> SearchRead:
    at = valid_at or utc_now()
    normalized, ranked, indexed_count, eligible_count = _vector_ranked(
        db, user_id=user_id, project_id=project_id, query=query, types=types,
        at=at, limit=top_k + 1, settings=settings,
    )
    truncated = len(ranked) > top_k
    ranked = ranked[:top_k]
    reads = graph._reads(db, [item[0] for item in ranked], at=at)
    evidence_by_entity = graph.evidence_for_records(db, [item[0] for item in ranked], at=at)
    items = [SearchHit(
        entity=read,
        vector_score=round(score, 6),
        matched_fields=[],
        evidence=evidence_by_entity[entity.id][:3],
    ) for (entity, score), read in zip(ranked, reads, strict=True)]
    return SearchRead(
        query=normalized, mode='vector', items=items, truncated=truncated,
        indexed_count=indexed_count, eligible_count=eligible_count,
    )


def _hybrid_search(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, query: str,
    types: list[str], valid_at: datetime | None, top_k: int, settings: Settings,
) -> SearchRead:
    at = valid_at or utc_now()
    normalized, _, keyword_ranked = _keyword_ranked(
        db, user_id=user_id, project_id=project_id, query=query, types=types,
        at=at, limit=HYBRID_POOL_LIMIT, strict_term_limit=False,
    )
    _, vector_ranked, indexed_count, eligible_count = _vector_ranked(
        db, user_id=user_id, project_id=project_id, query=normalized, types=types,
        at=at, limit=HYBRID_POOL_LIMIT, settings=settings,
    )
    candidates: dict[uuid.UUID, _HybridCandidate] = {}
    for entity, score, matched_fields in keyword_ranked:
        candidates[entity.id] = _HybridCandidate(
            entity=entity, keyword_score=score, matched_fields=matched_fields,
        )
    for entity, score in vector_ranked:
        candidate = candidates.setdefault(entity.id, _HybridCandidate(entity=entity))
        candidate.vector_score = score

    max_keyword = max((candidate.keyword_score for candidate in candidates.values()), default=0)
    seed_strength = {
        entity_id: max(
            candidate.keyword_score / max_keyword if max_keyword else 0.0,
            max(0.0, min(1.0, candidate.vector_score or 0.0)),
        )
        for entity_id, candidate in candidates.items()
    }
    seed_ids = set(seed_strength)
    edge_rows = []
    if seed_ids:
        edge_rows = list(db.scalars(
            graph._edge_query(user_id, project_id, at).where(or_(
                identities.canonical(KnowledgeRelationship.source_id, user_id, project_id, at).in_(seed_ids),
                identities.canonical(KnowledgeRelationship.target_id, user_id, project_id, at).in_(seed_ids),
            )).order_by(
                KnowledgeRelationship.confidence.desc(), KnowledgeRelationship.name,
                KnowledgeRelationship.id,
            ).limit(HYBRID_EDGE_LIMIT + 1)
        ))
    graph_truncated = len(edge_rows) > HYBRID_EDGE_LIMIT
    edge_rows = edge_rows[:HYBRID_EDGE_LIMIT]
    links = identities.mapping(db, user_id, project_id, at) if edge_rows else {}
    endpoints = lambda edge: (links.get(edge.source_id, edge.source_id), links.get(edge.target_id, edge.target_id))
    endpoint_ids = {identifier for edge in edge_rows for identifier in endpoints(edge)}
    eligible_entities = {
        entity.id: entity for entity in db.scalars(select(KnowledgeEntity).where(
            KnowledgeEntity.id.in_(endpoint_ids),
            *_base_conditions(user_id, project_id, at, types),
        ))
    } if endpoint_ids else {}

    signals: dict[uuid.UUID, list[GraphSearchSignal]] = {}
    for edge in edge_rows:
        source_id, target_id = endpoints(edge)
        for seed_id, candidate_id in ((source_id, target_id), (target_id, source_id)):
            strength = seed_strength.get(seed_id, 0.0)
            candidate_entity = eligible_entities.get(candidate_id)
            related_entity = eligible_entities.get(seed_id) or candidates.get(seed_id, None)
            if candidate_entity is None or candidate_id == seed_id or strength <= 0:
                continue
            related_name = (
                related_entity.entity.name if isinstance(related_entity, _HybridCandidate)
                else related_entity.name if related_entity is not None else ''
            )
            score = max(0.0, min(1.0, strength * edge.confidence))
            signals.setdefault(candidate_id, []).append(GraphSearchSignal(
                relationship_id=edge.id, relationship_type=edge.type,
                relationship_name=edge.name, related_entity_id=seed_id,
                related_entity_name=related_name, score=round(score, 6),
            ))
            candidate = candidates.setdefault(candidate_id, _HybridCandidate(entity=candidate_entity))
            candidate.graph_score = max(candidate.graph_score, score)

    for entity_id, candidate in candidates.items():
        candidate.graph_connections = sorted(
            signals.get(entity_id, []),
            key=lambda signal: (-signal.score, signal.relationship_name, str(signal.relationship_id)),
        )[:3]

    def components(candidate: _HybridCandidate):
        keyword = candidate.keyword_score / max_keyword if max_keyword else 0.0
        vector = max(0.0, min(1.0, candidate.vector_score or 0.0))
        graph_score = candidate.graph_score
        total = (
            HYBRID_WEIGHTS.keyword * keyword
            + HYBRID_WEIGHTS.vector * vector
            + HYBRID_WEIGHTS.graph * graph_score
        )
        return keyword, vector, graph_score, total

    ranked = sorted(
        ((candidate, *components(candidate)) for candidate in candidates.values()),
        key=lambda item: (-item[4], item[0].entity.name, str(item[0].entity.id)),
    )
    truncated = graph_truncated or len(ranked) > top_k
    ranked = ranked[:top_k]
    reads = graph._reads(db, [item[0].entity for item in ranked], at=at)
    evidence_by_entity = graph.evidence_for_records(db, [item[0].entity for item in ranked], at=at)
    items = []
    for item, read in zip(ranked, reads, strict=True):
        candidate, keyword_component, vector_component, graph_score, hybrid_score = item
        items.append(SearchHit(
            entity=read,
            keyword_score=candidate.keyword_score,
            vector_score=round(candidate.vector_score, 6) if candidate.vector_score is not None else None,
            keyword_component=round(keyword_component, 6),
            vector_component=round(vector_component, 6),
            graph_score=round(graph_score, 6), hybrid_score=round(hybrid_score, 6),
            matched_fields=candidate.matched_fields,
            graph_connections=candidate.graph_connections,
            evidence=evidence_by_entity[candidate.entity.id][:3],
        ))
    return SearchRead(
        query=normalized, mode='hybrid', items=items, truncated=truncated,
        indexed_count=indexed_count, eligible_count=eligible_count, weights=HYBRID_WEIGHTS,
    )


def search_knowledge(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, query: str,
    types: list[str], valid_at: datetime | None, top_k: int, mode: str,
    settings: Settings,
) -> SearchRead:
    get_project(db, user_id=user_id, project_id=project_id)
    if mode == 'rrf':
        from app.services.fusion import reciprocal_rank_search
        return reciprocal_rank_search(db, user_id=user_id, project_id=project_id, query=query,
                                      types=types, valid_at=valid_at, top_k=top_k, settings=settings)
    if mode in {'bm25', 'bm25_source'}:
        return _bm25_search(db, user_id=user_id, project_id=project_id, query=query,
                            types=types, valid_at=valid_at, top_k=top_k, provenance=mode == 'bm25_source')
    if mode == 'hybrid':
        return _hybrid_search(
            db, user_id=user_id, project_id=project_id, query=query, types=types,
            valid_at=valid_at, top_k=top_k, settings=settings,
        )
    if mode == 'vector':
        return _vector_search(
            db, user_id=user_id, project_id=project_id, query=query, types=types,
            valid_at=valid_at, top_k=top_k, settings=settings,
        )
    return _keyword_search(
        db, user_id=user_id, project_id=project_id, query=query, types=types,
        valid_at=valid_at, top_k=top_k,
    )
