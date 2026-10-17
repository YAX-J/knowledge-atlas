import hashlib
import uuid
from datetime import datetime
from typing import get_args

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.errors import AppError
from app.models.domain import CandidateKnowledge, ProcessingTask, ReviewStatus, SourceChunk, SourceDocument, TaskStatus, utc_now
from app.models.graph import KnowledgeEntity, KnowledgeEvidence, KnowledgeRelationship
from app.schemas.graph import EntityDetail, FormalEvidenceRead, GraphRead, KnowledgeEdgeRead, KnowledgeNodeRead, RelationshipDetail
from app.schemas.knowledge import EntityType, EvidenceDraft, RelationType
from app.services.projects import get_project


MAX_EDGES = 500


def knowledge_ids(db: Session, candidates: list[CandidateKnowledge]) -> dict[uuid.UUID, uuid.UUID]:
    if not candidates:
        return {}
    result = {}
    for model in (KnowledgeEntity, KnowledgeRelationship):
        result.update(db.execute(select(model.candidate_id, model.id).where(
            model.candidate_id.in_([item.id for item in candidates]),
            model.user_id == candidates[0].user_id, model.project_id == candidates[0].project_id,
        )).all())
    return result


def _promotion_error():
    return AppError(status_code=409, code="KNOWLEDGE_PROMOTION_INVALID", message="候选的类型、端点或证据无法写入正式知识，请核对来源")


def _evidence_for_promotion(db: Session, candidate: CandidateKnowledge):
    source = db.scalar(select(SourceDocument).join(ProcessingTask, ProcessingTask.source_id == SourceDocument.id).where(
        SourceDocument.id == candidate.source_id, SourceDocument.user_id == candidate.user_id,
        SourceDocument.project_id == candidate.project_id,
        ProcessingTask.id == candidate.task_id, ProcessingTask.user_id == candidate.user_id,
        ProcessingTask.project_id == candidate.project_id, ProcessingTask.type == "knowledge_candidates",
        ProcessingTask.status == TaskStatus.SUCCEEDED,
    ))
    if source is None or candidate.review_status != ReviewStatus.CONFIRMED:
        raise _promotion_error()
    try:
        raw = candidate.payload["evidence"]
        if not isinstance(raw, list) or not 1 <= len(raw) <= 5:
            raise ValueError("Invalid evidence count")
        refs = [EvidenceDraft.model_validate({"chunk_id": item["chunk_id"], "quote": item["quote"]}) for item in raw]
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise _promotion_error() from exc
    chunks = {chunk.id: chunk for chunk in db.scalars(select(SourceChunk).where(
        SourceChunk.id.in_([ref.chunk_id for ref in refs]), SourceChunk.source_id == candidate.source_id,
        SourceChunk.user_id == candidate.user_id, SourceChunk.project_id == candidate.project_id,
    ))}
    validated = []
    for ref in refs:
        chunk = chunks.get(ref.chunk_id)
        if chunk is None or ref.quote not in chunk.content:
            raise _promotion_error()
        start = chunk.content.index(ref.quote)
        line = chunk.start_line + chunk.content[:start].count("\n")
        validated.append((chunk, ref.quote, line, line + ref.quote.count("\n")))
    return validated


def promote_candidate(
    db: Session, candidate: CandidateKnowledge, endpoints: list[CandidateKnowledge] | None = None,
) -> uuid.UUID:
    """Called under the review project's lock; caller owns commit/rollback."""
    relation = candidate.payload.get("kind") == "relation"
    if candidate.payload.get("kind") not in {"entity", "relation"}:
        raise _promotion_error()
    model = KnowledgeRelationship if relation else KnowledgeEntity
    existing = db.scalar(select(model).where(
        model.candidate_id == candidate.id, model.user_id == candidate.user_id, model.project_id == candidate.project_id,
    ))
    if existing is not None:
        return existing.id
    allowed = get_args(RelationType if relation else EntityType)
    if candidate.candidate_type not in allowed or not candidate.name.strip() or not candidate.summary.strip():
        raise _promotion_error()
    evidence = _evidence_for_promotion(db, candidate)
    endpoint_ids = {}
    if relation:
        try:
            refs = {key: uuid.UUID(candidate.payload[key]) for key in ("source_candidate_id", "target_candidate_id")}
        except (KeyError, TypeError, ValueError) as exc:
            raise _promotion_error() from exc
        by_id = {item.id: item for item in endpoints or []}
        for key, endpoint_id in refs.items():
            endpoint = by_id.get(endpoint_id)
            if endpoint is None or endpoint.payload.get("kind") != "entity" or (
                endpoint.user_id, endpoint.project_id, endpoint.source_id, endpoint.task_id
            ) != (candidate.user_id, candidate.project_id, candidate.source_id, candidate.task_id):
                raise _promotion_error()
            endpoint_ids["source_id" if key == "source_candidate_id" else "target_id"] = promote_candidate(db, endpoint)
    formal_id = uuid.uuid5(candidate.id, "formal-relationship-v1" if relation else "formal-entity-v1")
    record = model(
        id=formal_id, candidate_id=candidate.id, user_id=candidate.user_id, project_id=candidate.project_id,
        type=candidate.candidate_type, name=candidate.name, summary=candidate.summary,
        confidence=candidate.confidence, status="active", valid_from=utc_now(), valid_to=None, **endpoint_ids,
    )
    db.add(record)
    db.flush()
    ids = set()
    for chunk, quote, start, end in evidence:
        evidence_id = uuid.uuid5(formal_id, f"{chunk.id}:{hashlib.sha256(quote.encode()).hexdigest()}")
        if evidence_id in ids:
            continue
        ids.add(evidence_id)
        db.add(KnowledgeEvidence(
            id=evidence_id, user_id=candidate.user_id, project_id=candidate.project_id,
            source_id=candidate.source_id, chunk_id=chunk.id,
            entity_id=None if relation else formal_id, relationship_id=formal_id if relation else None,
            quote=quote, start_line=start, end_line=end, heading_path=chunk.heading_path,
        ))
    db.flush()
    return formal_id


def visible(model, user_id: uuid.UUID, project_id: uuid.UUID, at: datetime):
    return (
        model.user_id == user_id, model.project_id == project_id, model.status != "archived",
        model.valid_from <= at, or_(model.valid_to.is_(None), model.valid_to > at),
    )


def _edge_query(user_id: uuid.UUID, project_id: uuid.UUID, at: datetime):
    source, target = aliased(KnowledgeEntity), aliased(KnowledgeEntity)
    return select(KnowledgeRelationship).join(source, source.id == KnowledgeRelationship.source_id).join(
        target, target.id == KnowledgeRelationship.target_id,
    ).where(*visible(KnowledgeRelationship, user_id, project_id, at),
            *visible(source, user_id, project_id, at), *visible(target, user_id, project_id, at))


def _reads(db: Session, records, *, edges=False):
    if not records:
        return []
    owner = KnowledgeEvidence.relationship_id if edges else KnowledgeEvidence.entity_id
    counts = dict(db.execute(select(owner, func.count()).where(
        owner.in_([item.id for item in records]), KnowledgeEvidence.user_id == records[0].user_id,
        KnowledgeEvidence.project_id == records[0].project_id,
    ).group_by(owner)).all())
    schema = KnowledgeEdgeRead if edges else KnowledgeNodeRead
    return [schema.model_validate(item).model_copy(update={"evidence_count": counts.get(item.id, 0)}) for item in records]


def get_graph(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, center_id: uuid.UUID | None,
    depth: int, types: list[str], valid_at: datetime | None, limit: int,
) -> GraphRead:
    get_project(db, user_id=user_id, project_id=project_id)
    at = valid_at or utc_now()
    node_query = select(KnowledgeEntity).where(*visible(KnowledgeEntity, user_id, project_id, at))
    if types:
        node_query = node_query.where(KnowledgeEntity.type.in_(types))
    ordered_nodes = node_query.order_by(KnowledgeEntity.created_at, KnowledgeEntity.id)
    edge_query = _edge_query(user_id, project_id, at)
    truncated = False
    if center_id is None:
        nodes = list(db.scalars(ordered_nodes.limit(limit + 1)))
        truncated = len(nodes) > limit
        nodes = nodes[:limit]
    else:
        center = db.scalar(node_query.where(KnowledgeEntity.id == center_id))
        if center is None:
            raise AppError(status_code=404, code="KNOWLEDGE_NOT_FOUND", message="中心知识不存在或不符合当前筛选条件")
        nodes = [center]
        frontier, visited = {center_id}, {center_id}
        for _ in range(depth):
            outgoing = edge_query.with_only_columns(KnowledgeRelationship.target_id).where(KnowledgeRelationship.source_id.in_(frontier))
            incoming = edge_query.with_only_columns(KnowledgeRelationship.source_id).where(KnowledgeRelationship.target_id.in_(frontier))
            neighbors = outgoing.union(incoming).subquery()
            remaining = limit - len(nodes)
            found = list(db.scalars(ordered_nodes.where(
                KnowledgeEntity.id.in_(select(neighbors)), KnowledgeEntity.id.not_in(visited),
            ).limit(remaining + 1)))
            truncated = truncated or len(found) > remaining
            found = found[:remaining]
            nodes.extend(found)
            frontier = {item.id for item in found}
            visited.update(frontier)
            if not frontier:
                break
    ids = [node.id for node in nodes]
    edges = list(db.scalars(edge_query.where(
        KnowledgeRelationship.source_id.in_(ids), KnowledgeRelationship.target_id.in_(ids),
    ).order_by(KnowledgeRelationship.created_at, KnowledgeRelationship.id).limit(MAX_EDGES + 1))) if ids else []
    truncated = truncated or len(edges) > MAX_EDGES
    return GraphRead(nodes=_reads(db, nodes), edges=_reads(db, edges[:MAX_EDGES], edges=True), truncated=truncated)


def _evidence_read(db: Session, record):
    owner = KnowledgeEvidence.entity_id if isinstance(record, KnowledgeEntity) else KnowledgeEvidence.relationship_id
    rows = db.execute(select(KnowledgeEvidence, SourceDocument.original_name).join(
        SourceDocument, SourceDocument.id == KnowledgeEvidence.source_id,
    ).join(SourceChunk, SourceChunk.id == KnowledgeEvidence.chunk_id).where(
        owner == record.id, KnowledgeEvidence.user_id == record.user_id, KnowledgeEvidence.project_id == record.project_id,
        SourceDocument.user_id == record.user_id, SourceDocument.project_id == record.project_id,
        SourceChunk.source_id == KnowledgeEvidence.source_id,
        SourceChunk.user_id == record.user_id, SourceChunk.project_id == record.project_id,
    ).order_by(KnowledgeEvidence.start_line, KnowledgeEvidence.id))
    return [FormalEvidenceRead(
        id=item.id, source_id=item.source_id, chunk_id=item.chunk_id, title=title,
        uri=f"project://{record.project_id}/sources/{item.source_id}", quote=item.quote,
        start_line=item.start_line, end_line=item.end_line, heading_path=item.heading_path,
    ) for item, title in rows]


def entity_detail(db: Session, *, user_id: uuid.UUID, entity_id: uuid.UUID, valid_at: datetime | None) -> EntityDetail:
    entity = db.scalar(select(KnowledgeEntity).where(KnowledgeEntity.id == entity_id, KnowledgeEntity.user_id == user_id))
    if entity is None:
        raise AppError(status_code=404, code="KNOWLEDGE_NOT_FOUND", message="知识不存在")
    get_project(db, user_id=user_id, project_id=entity.project_id)
    at = valid_at or utc_now()
    if db.scalar(select(KnowledgeEntity.id).where(KnowledgeEntity.id == entity_id, *visible(KnowledgeEntity, user_id, entity.project_id, at))) is None:
        raise AppError(status_code=404, code="KNOWLEDGE_NOT_FOUND", message="知识在当前时间不可见")
    edges = list(db.scalars(_edge_query(user_id, entity.project_id, at).where(or_(
        KnowledgeRelationship.source_id == entity_id, KnowledgeRelationship.target_id == entity_id,
    )).order_by(KnowledgeRelationship.created_at, KnowledgeRelationship.id).limit(101)))
    evidence = _evidence_read(db, entity)
    return EntityDetail(entity=_reads(db, [entity])[0], evidence=evidence,
                        relationships=_reads(db, edges[:100], edges=True), truncated=len(edges) > 100)


def relationship_detail(db: Session, *, user_id: uuid.UUID, relationship_id: uuid.UUID, valid_at: datetime | None) -> RelationshipDetail:
    edge = db.scalar(select(KnowledgeRelationship).where(KnowledgeRelationship.id == relationship_id, KnowledgeRelationship.user_id == user_id))
    if edge is None:
        raise AppError(status_code=404, code="KNOWLEDGE_NOT_FOUND", message="关系不存在")
    get_project(db, user_id=user_id, project_id=edge.project_id)
    if db.scalar(_edge_query(user_id, edge.project_id, valid_at or utc_now()).where(KnowledgeRelationship.id == relationship_id)) is None:
        raise AppError(status_code=404, code="KNOWLEDGE_NOT_FOUND", message="关系在当前时间不可见")
    return RelationshipDetail(relationship=_reads(db, [edge], edges=True)[0], evidence=_evidence_read(db, edge))
