"""Bind question evidence to its graph owner and to the requested graph instant."""

from sqlalchemy import or_, select, tuple_

from app.models.graph import KnowledgeEntity, KnowledgeEvidence, KnowledgeRelationship
from app.schemas.questions import EvidenceEntityRead, EvidenceRelationshipRead, QuestionEvidenceRead
from app.services import graph, identities


MAX_RELATIONSHIP_EDGES = 24
PASSAGE_FIELDS = ("source_id", "chunk_id", "start_line", "end_line", "quote")


def passage(item):
    return tuple(getattr(item, field) for field in PASSAGE_FIELDS)


def relationship_passages(db, user_id, project_id, evidence):
    if not evidence:
        return set()
    # A shared entity quote must not reintroduce a relationship that is outside the question's time.
    fields = [getattr(KnowledgeEvidence, field) for field in PASSAGE_FIELDS]
    return {tuple(row) for row in db.execute(select(*fields).where(
        KnowledgeEvidence.user_id == user_id, KnowledgeEvidence.project_id == project_id,
        KnowledgeEvidence.relationship_id.is_not(None),
        tuple_(*fields).in_([passage(item) for item in evidence]),
    ).distinct())}


def scoped_evidence(db, *, user_id, project_id, at, hits):
    if not hits:
        return [], False
    entity_ids = [hit.entity.id for hit in hits]
    edge = KnowledgeRelationship
    source = identities.canonical(edge.source_id, user_id, project_id, at)
    target = identities.canonical(edge.target_id, user_id, project_id, at)
    edges = list(db.scalars(graph._edge_query(user_id, project_id, at).where(
        or_(source.in_(entity_ids), target.in_(entity_ids)),
    ).order_by(edge.confidence.desc(), edge.id).limit(MAX_RELATIONSHIP_EDGES + 1)))
    truncated = len(edges) > MAX_RELATIONSHIP_EDGES
    edges = edges[:MAX_RELATIONSHIP_EDGES]
    return edge_evidence(db, edges, user_id, project_id, at, entity_ids), truncated


def edge_evidence(db, edges, user_id, project_id, at, entity_ids=()):
    if not edges:
        return []

    reads = graph._reads(db, edges, edges=True, at=at)
    endpoint_ids = {identifier for item in reads for identifier in (item.source_id, item.target_id)}
    names = dict(db.execute(select(KnowledgeEntity.id, KnowledgeEntity.name).where(
        KnowledgeEntity.user_id == user_id, KnowledgeEntity.project_id == project_id,
        KnowledgeEntity.id.in_(endpoint_ids),
    )).all())
    evidence = graph.evidence_for_records(db, edges, at=at)
    rank = {identifier: index for index, identifier in enumerate(entity_ids)}
    reads.sort(key=lambda item: min(rank.get(item.source_id, len(rank)), rank.get(item.target_id, len(rank))))
    results = []
    for item in reads:
        source_ref = EvidenceEntityRead(id=item.source_id, name=names[item.source_id])
        target_ref = EvidenceEntityRead(id=item.target_id, name=names[item.target_id])
        relationship = EvidenceRelationshipRead(
            id=item.id, type=item.type, source=source_ref, target=target_ref,
            valid_at=at, valid_from=item.valid_from, valid_to=item.valid_to,
        )
        related = list({ref.id: ref for ref in [source_ref, target_ref] if not rank or ref.id in rank}.values())
        related.sort(key=lambda ref: rank.get(ref.id, len(rank)))
        results.extend(QuestionEvidenceRead(
            **quote.model_dump(), entity_id=related[0].id, entity_name=related[0].name,
            related_entities=related, relationship=relationship,
        ) for quote in evidence[item.id])
    return results
