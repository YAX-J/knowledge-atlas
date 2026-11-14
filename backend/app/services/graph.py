import hashlib
import uuid
from datetime import datetime, timezone
from typing import get_args

from pydantic import ValidationError
from sqlalchemy import and_, func, or_, select, union
from sqlalchemy.orm import Session, aliased

from app.core.errors import AppError
from app.models.domain import (
    CandidateKnowledge,
    ProcessingTask,
    ReviewStatus,
    SourceChunk,
    SourceDocument,
    SourceRepository,
    TaskStatus,
    utc_now,
)
from app.models.graph import KnowledgeEntity, KnowledgeEvidence, KnowledgeRelationship
from app.models.workspace import EntityMerge, KnowledgePeriod
from app.services import identities
from app.schemas.graph import EntityDetail, FormalEvidenceRead, GraphRead, GraphTimelineRead, KnowledgeEdgeRead, KnowledgeNodeRead, RelationshipDetail
from app.schemas.knowledge import EntityType, EvidenceDraft, FactValidity, RelationType
from app.services.projects import get_project
from app.services.source_links import github_file_urls, github_line_url


MAX_EDGES = 500
MAX_TIMELINE_INSTANTS = 200
NEO4J_MAX_NODES = 5000
NEO4J_MAX_EDGES = 20000


def apply_retirement(record, event):
    """Called only by explicit retirement under the project lock; caller commits."""
    event.before = {key: str(getattr(record, key)) if key in {'id', 'candidate_id'} else getattr(record, key)
                    for key in ('id', 'candidate_id', 'type', 'name', 'summary', 'confidence', 'status')}
    event.before.update(valid_from=(record.valid_from.replace(tzinfo=timezone.utc) if record.valid_from.tzinfo is None
        else record.valid_from.astimezone(timezone.utc)).isoformat(), valid_to=None)
    if isinstance(record, KnowledgeRelationship):
        event.before.update(source_id=str(record.source_id), target_id=str(record.target_id))
    record.valid_to = event.effective_at
    event.after = {**event.before, 'valid_to': event.effective_at.isoformat()}


def apply_reviewed_change(change, new, old, *, confirm: bool):
    """Evolution service validates evidence and holds the project lock; caller commits."""
    def snapshot(entity):
        def iso(value):
            return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()
        return {"id": str(entity.id), "status": entity.status,
                "valid_from": iso(entity.valid_from),
                "valid_to": iso(entity.valid_to) if entity.valid_to else None}

    change.before = {"new": snapshot(new), "old": snapshot(old)}
    if confirm and change.kind == "SUPERSEDES":
        old.status, old.valid_to = "superseded", change.effective_at
        new.valid_from = change.effective_at
    change.after = {"new": snapshot(new), "old": snapshot(old)}
    change.resolved_at = utc_now()
    change.review_status = "confirmed" if confirm else "rejected"


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
    *, canonical_source_id: uuid.UUID | None = None,
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
    try:
        validity = FactValidity.model_validate(candidate.payload["validity"]) if candidate.payload.get("validity") else None
    except ValidationError as exc:
        raise _promotion_error() from exc
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
            formal_endpoint_id = (canonical_source_id if key == "source_candidate_id" and canonical_source_id
                                  else promote_candidate(db, endpoint))
            if validity is not None:
                # An explicit relation interval must fit the approved intervals of both endpoints.
                formal_endpoint = db.get(KnowledgeEntity, formal_endpoint_id)
                start = formal_endpoint.valid_from
                end = formal_endpoint.valid_to
                if (validity.valid_from < (start if start.tzinfo else start.replace(tzinfo=timezone.utc))
                        or (end is not None and (validity.valid_to is None
                            or validity.valid_to > (end if end.tzinfo else end.replace(tzinfo=timezone.utc))))):
                    raise AppError(status_code=409, code="REVIEW_VALIDITY_OUTSIDE_ENDPOINTS",
                                   message="关系的有效期须落在两端实体的有效期内，请核对并修正时间")
            endpoint_ids["source_id" if key == "source_candidate_id" else "target_id"] = formal_endpoint_id
    formal_id = uuid.uuid5(candidate.id, "formal-relationship-v1" if relation else "formal-entity-v1")
    record = model(
        id=formal_id, candidate_id=candidate.id, user_id=candidate.user_id, project_id=candidate.project_id,
        type=candidate.candidate_type, name=candidate.name, summary=candidate.summary,
        confidence=candidate.confidence, status="active",
        valid_from=validity.valid_from if validity else utc_now(), valid_to=validity.valid_to if validity else None,
        **endpoint_ids,
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


def apply_relationship_replacement(db: Session, old_id: uuid.UUID, new_id: uuid.UUID, effective_at: datetime):
    """Close the approved predecessor under the review project lock and return audit snapshots."""
    old = db.get(KnowledgeRelationship, old_id)
    new = db.get(KnowledgeRelationship, new_id)
    before = KnowledgeEdgeRead.model_validate(old).model_dump(mode="json")
    old.valid_to = effective_at
    old.status = "superseded"
    return before, {
        "kind": "SUPERSEDES",
        "old": KnowledgeEdgeRead.model_validate(old).model_dump(mode="json"),
        "new": KnowledgeEdgeRead.model_validate(new).model_dump(mode="json"),
    }


def apply_lifecycle(db, record, request, now, *, current):
    """Authorized human mutation boundary; caller holds the project lock."""
    if request.action == 'withdraw':
        if not current or record.valid_to is not None:
            raise AppError(status_code=409, code='KNOWLEDGE_NOT_CURRENT', message='只能撤回当前有效知识')
        record.valid_to = now
    elif request.action == 'reactivate':
        if current or record.valid_to is None or record.status == 'archived':
            raise AppError(status_code=409, code='KNOWLEDGE_NOT_CLOSED', message='请选择已停用或撤回的知识')
        if not _evidence_read(db, record):
            raise AppError(status_code=409, code='KNOWLEDGE_EVIDENCE_INVALID', message='重新启用需要原始证据')
        if isinstance(record, KnowledgeEntity) and db.scalar(select(EntityMerge.id).where(
                *identities.active_merge(record.user_id, record.project_id, now), EntityMerge.source_id == record.id)):
            raise AppError(status_code=409, code='KNOWLEDGE_MERGED', message='请先解除合并身份')
        if isinstance(record, KnowledgeRelationship):
            for endpoint in (record.source_id, record.target_id):
                target = db.scalar(select(identities.canonical(KnowledgeEntity.id, record.user_id, record.project_id, now)).where(KnowledgeEntity.id == endpoint))
                if db.scalar(select(KnowledgeEntity.id).where(KnowledgeEntity.id == target,
                        *visible(KnowledgeEntity, record.user_id, record.project_id, now))) is None:
                    raise AppError(status_code=409, code='KNOWLEDGE_ENDPOINT_CLOSED', message='请先重新启用关系两端实体')
        db.add(KnowledgePeriod(user_id=record.user_id, project_id=record.project_id, knowledge_id=record.id,
            kind=request.kind, valid_from=record.valid_from, valid_to=record.valid_to))
        record.valid_from, record.valid_to, record.status = now, None, 'active'


def apply_evolution_group(records, old_ids, now):
    """A reviewed split/merge closes predecessors together; existing successor history stays intact."""
    for key in old_ids:
        records[key].valid_to, records[key].status = now, 'superseded'


def visible(model, user_id: uuid.UUID, project_id: uuid.UUID, at: datetime):
    is_entity = model.__tablename__ == 'knowledge_entities'
    previous = select(KnowledgePeriod.id).where(
        KnowledgePeriod.user_id == user_id, KnowledgePeriod.project_id == project_id,
        KnowledgePeriod.kind == ('entity' if is_entity else 'relationship'),
        KnowledgePeriod.knowledge_id == model.id, KnowledgePeriod.valid_from <= at,
        KnowledgePeriod.valid_to > at,
    ).correlate_except(KnowledgePeriod).exists()
    conditions = [
        model.user_id == user_id, model.project_id == project_id, model.status != "archived",
        or_(and_(model.valid_from <= at, or_(model.valid_to.is_(None), model.valid_to > at)), previous),
    ]
    if is_entity:
        conditions.append(~select(EntityMerge.id).where(*identities.active_merge(user_id, project_id, at),
            EntityMerge.source_id == model.id).correlate_except(EntityMerge).exists())
    return tuple(conditions)


def _edge_query(user_id: uuid.UUID, project_id: uuid.UUID, at: datetime):
    source, target = aliased(KnowledgeEntity), aliased(KnowledgeEntity)
    return select(KnowledgeRelationship).join(source, source.id == identities.canonical(KnowledgeRelationship.source_id, user_id, project_id, at)).join(
        target, target.id == identities.canonical(KnowledgeRelationship.target_id, user_id, project_id, at),
    ).where(*visible(KnowledgeRelationship, user_id, project_id, at),
            *visible(source, user_id, project_id, at), *visible(target, user_id, project_id, at))


def _reads(db: Session, records, *, edges=False, at=None):
    if not records:
        return []
    at = at or utc_now()
    owner = KnowledgeEvidence.relationship_id if edges else identities.canonical(KnowledgeEvidence.entity_id, records[0].user_id, records[0].project_id, at)
    counts = dict(db.execute(select(owner, func.count()).where(
        owner.in_([item.id for item in records]), KnowledgeEvidence.user_id == records[0].user_id,
        KnowledgeEvidence.project_id == records[0].project_id,
    ).group_by(owner)).all())
    schema = KnowledgeEdgeRead if edges else KnowledgeNodeRead
    result = [schema.model_validate(item).model_copy(update={"evidence_count": counts.get(item.id, 0)}) for item in records]
    if edges:
        links = identities.mapping(db, records[0].user_id, records[0].project_id, at)
        for item in result:
            item.source_id = links.get(item.source_id, item.source_id)
            item.target_id = links.get(item.target_id, item.target_id)
    periods = list(db.scalars(select(KnowledgePeriod).where(
        KnowledgePeriod.user_id == records[0].user_id, KnowledgePeriod.project_id == records[0].project_id,
        KnowledgePeriod.kind == ('relationship' if edges else 'entity'), KnowledgePeriod.knowledge_id.in_([r.id for r in records]),
        KnowledgePeriod.valid_from <= at, KnowledgePeriod.valid_to > at)))
    intervals = {item.knowledge_id: item for item in periods}
    for item in result:
        if item.id in intervals:
            item.valid_from, item.valid_to, item.status = intervals[item.id].valid_from, intervals[item.id].valid_to, 'active'
    return result


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
            source_id = identities.canonical(KnowledgeRelationship.source_id, user_id, project_id, at)
            target_id = identities.canonical(KnowledgeRelationship.target_id, user_id, project_id, at)
            outgoing = edge_query.with_only_columns(target_id).where(source_id.in_(frontier))
            incoming = edge_query.with_only_columns(source_id).where(target_id.in_(frontier))
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
        identities.canonical(KnowledgeRelationship.source_id, user_id, project_id, at).in_(ids),
        identities.canonical(KnowledgeRelationship.target_id, user_id, project_id, at).in_(ids),
    ).order_by(KnowledgeRelationship.created_at, KnowledgeRelationship.id).limit(MAX_EDGES + 1))) if ids else []
    truncated = truncated or len(edges) > MAX_EDGES
    return GraphRead(nodes=_reads(db, nodes, at=at), edges=_reads(db, edges[:MAX_EDGES], edges=True, at=at), truncated=truncated)


def timeline(db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID) -> GraphTimelineRead:
    get_project(db, user_id=user_id, project_id=project_id)
    now = utc_now()
    boundaries = []
    for record, kind in ((KnowledgeEntity, 'entity'), (KnowledgeRelationship, 'relationship')):
        scope = (record.user_id == user_id, record.project_id == project_id, record.status != 'archived')
        for field in ('valid_from', 'valid_to'):
            boundary = getattr(record, field)
            boundaries.append(select(boundary.label('instant')).where(
                *scope, boundary <= now, or_(record.valid_to.is_(None), record.valid_from < record.valid_to),
            ))
            saved = getattr(KnowledgePeriod, field)
            boundaries.append(select(saved.label('instant')).join(record, and_(
                record.id == KnowledgePeriod.knowledge_id, record.user_id == KnowledgePeriod.user_id,
                record.project_id == KnowledgePeriod.project_id,
            )).where(*scope, KnowledgePeriod.kind == kind, saved <= now,
                     KnowledgePeriod.valid_from < KnowledgePeriod.valid_to))
    for boundary in (EntityMerge.valid_from, EntityMerge.valid_to):
        boundaries.append(select(boundary.label('instant')).where(
            EntityMerge.user_id == user_id, EntityMerge.project_id == project_id, boundary <= now,
            or_(EntityMerge.valid_to.is_(None), EntityMerge.valid_from < EntityMerge.valid_to),
        ))
    instants = union(*boundaries).subquery().c.instant
    newest_first = list(db.scalars(select(instants).order_by(instants.desc()).limit(MAX_TIMELINE_INSTANTS + 1)))
    return GraphTimelineRead(
        instants=[value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
                  for value in reversed(newest_first[:MAX_TIMELINE_INSTANTS])],
        truncated=len(newest_first) > MAX_TIMELINE_INSTANTS,
    )


def read_projection(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, at: datetime,
) -> GraphRead:
    """Read the full visible graph under the project lock held by the caller."""
    nodes = list(db.scalars(select(KnowledgeEntity).where(
        *visible(KnowledgeEntity, user_id, project_id, at),
    ).order_by(KnowledgeEntity.created_at, KnowledgeEntity.id).limit(NEO4J_MAX_NODES + 1)))
    edges = list(db.scalars(_edge_query(user_id, project_id, at).order_by(
        KnowledgeRelationship.created_at, KnowledgeRelationship.id,
    ).limit(NEO4J_MAX_EDGES + 1)))
    if len(nodes) > NEO4J_MAX_NODES or len(edges) > NEO4J_MAX_EDGES:
        raise AppError(status_code=409, code="NEO4J_PROJECTION_TOO_LARGE", message="项目图谱超过 Neo4j 快照上限")
    return GraphRead(nodes=_reads(db, nodes, at=at), edges=_reads(db, edges, edges=True, at=at), truncated=False)


def _evidence_read(db: Session, record):
    return evidence_for_records(db, [record])[record.id]


def evidence_for_records(db: Session, records, *, at=None):
    """Batch one homogeneous authorized scope; preserve each owner's evidence order."""
    if not records:
        return {}
    record = records[0]
    if any((item.user_id, item.project_id, isinstance(item, KnowledgeEntity)) !=
           (record.user_id, record.project_id, isinstance(record, KnowledgeEntity)) for item in records):
        raise ValueError('Evidence batch must share scope and owner kind')
    result = {item.id: [] for item in records}
    at = at or utc_now()
    owner = KnowledgeEvidence.entity_id if isinstance(record, KnowledgeEntity) else KnowledgeEvidence.relationship_id
    projected_owner = identities.canonical(owner, record.user_id, record.project_id, at) if isinstance(record, KnowledgeEntity) else owner
    rows = list(db.execute(select(
        KnowledgeEvidence,
        SourceDocument.original_name,
        SourceDocument.relative_path,
        SourceRepository.name,
    ).join(
        SourceDocument, SourceDocument.id == KnowledgeEvidence.source_id,
    ).outerjoin(
        SourceRepository,
        and_(
            SourceRepository.id == SourceDocument.repository_id,
            SourceRepository.user_id == record.user_id,
            SourceRepository.project_id == record.project_id,
        ),
    ).join(SourceChunk, SourceChunk.id == KnowledgeEvidence.chunk_id).where(
        projected_owner.in_(result), KnowledgeEvidence.user_id == record.user_id, KnowledgeEvidence.project_id == record.project_id,
        SourceDocument.user_id == record.user_id, SourceDocument.project_id == record.project_id,
        SourceChunk.source_id == KnowledgeEvidence.source_id,
        SourceChunk.user_id == record.user_id, SourceChunk.project_id == record.project_id,
    ).order_by(KnowledgeEvidence.start_line, KnowledgeEvidence.id)))
    git_urls = github_file_urls(
        db,
        user_id=record.user_id,
        project_id=record.project_id,
        source_ids=list({item.source_id for item, *_ in rows}),
    )
    links = identities.mapping(db, record.user_id, record.project_id, at) if isinstance(record, KnowledgeEntity) else {}
    for item, title, relative_path, repository_name in rows:
        owner_id = links.get(item.entity_id, item.entity_id) if isinstance(record, KnowledgeEntity) else item.relationship_id
        result[owner_id].append(FormalEvidenceRead(
        id=item.id, source_id=item.source_id, chunk_id=item.chunk_id,
        title=(
            f"{repository_name}/{relative_path}"
            if repository_name and relative_path else relative_path or title
        ),
        uri=f"project://{record.project_id}/sources/{item.source_id}", quote=item.quote,
        git_url=github_line_url(
            git_urls.get(item.source_id),
            start_line=item.start_line,
            end_line=item.end_line,
        ),
        start_line=item.start_line, end_line=item.end_line, heading_path=item.heading_path,
        ))
    return result


def entity_detail(db: Session, *, user_id: uuid.UUID, entity_id: uuid.UUID, valid_at: datetime | None) -> EntityDetail:
    entity = db.scalar(select(KnowledgeEntity).where(KnowledgeEntity.id == entity_id, KnowledgeEntity.user_id == user_id))
    if entity is None:
        raise AppError(status_code=404, code="KNOWLEDGE_NOT_FOUND", message="知识不存在")
    get_project(db, user_id=user_id, project_id=entity.project_id)
    at = valid_at or utc_now()
    if db.scalar(select(KnowledgeEntity.id).where(KnowledgeEntity.id == entity_id, *visible(KnowledgeEntity, user_id, entity.project_id, at))) is None:
        raise AppError(status_code=404, code="KNOWLEDGE_NOT_FOUND", message="知识在当前时间不可见")
    edges = list(db.scalars(_edge_query(user_id, entity.project_id, at).where(or_(
        identities.canonical(KnowledgeRelationship.source_id, user_id, entity.project_id, at) == entity_id,
        identities.canonical(KnowledgeRelationship.target_id, user_id, entity.project_id, at) == entity_id,
    )).order_by(KnowledgeRelationship.created_at, KnowledgeRelationship.id).limit(101)))
    evidence = evidence_for_records(db, [entity], at=at)[entity.id]
    return EntityDetail(entity=_reads(db, [entity], at=at)[0], evidence=evidence,
                        relationships=_reads(db, edges[:100], edges=True, at=at), truncated=len(edges) > 100)


def relationship_detail(db: Session, *, user_id: uuid.UUID, relationship_id: uuid.UUID, valid_at: datetime | None) -> RelationshipDetail:
    edge = db.scalar(select(KnowledgeRelationship).where(KnowledgeRelationship.id == relationship_id, KnowledgeRelationship.user_id == user_id))
    if edge is None:
        raise AppError(status_code=404, code="KNOWLEDGE_NOT_FOUND", message="关系不存在")
    get_project(db, user_id=user_id, project_id=edge.project_id)
    if db.scalar(_edge_query(user_id, edge.project_id, valid_at or utc_now()).where(KnowledgeRelationship.id == relationship_id)) is None:
        raise AppError(status_code=404, code="KNOWLEDGE_NOT_FOUND", message="关系在当前时间不可见")
    return RelationshipDetail(relationship=_reads(db, [edge], edges=True, at=valid_at)[0], evidence=_evidence_read(db, edge))
