"""Bounded, explicit human review of cross-source knowledge evolution."""
import hashlib
import json
import unicodedata
import uuid
from datetime import timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.domain import Project, SourceChunk, SourceDocument, utc_now
from app.models.evolution import KnowledgeChange
from app.models.graph import KnowledgeEntity, KnowledgeEvidence, KnowledgeRelationship
from app.schemas.evolution import ChangeCreate, ChangeList, ChangeRead, EvolutionRead, GovernanceFinding, GovernanceRead
from app.services import graph
from app.services.projects import get_project

MAX_HISTORY_ENTITIES = 100
MAX_HISTORY_CHANGES = 200
MAX_GOVERNANCE_ENTITIES = 1000


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _scope(user_id, project_id):
    return KnowledgeChange.user_id == user_id, KnowledgeChange.project_id == project_id


def _entity(db, user_id, project_id, entity_id):
    entity = db.scalar(select(KnowledgeEntity).where(
        KnowledgeEntity.id == entity_id, KnowledgeEntity.user_id == user_id, KnowledgeEntity.project_id == project_id,
    ).execution_options(populate_existing=True))
    if entity is None:
        raise AppError(status_code=404, code="KNOWLEDGE_NOT_FOUND", message="知识不存在或不属于此项目")
    return entity


def valid_evidence(db, entity):
    result = []
    for evidence in graph._evidence_read(db, entity):
        chunk = db.get(SourceChunk, evidence.chunk_id)
        if chunk is not None and evidence.quote and evidence.quote in chunk.content:
            result.append(evidence)
    return result


def _selected_evidence(db, change, new, old):
    evidence = [item for entity in (new, old) for item in valid_evidence(db, entity) if item.id == change.evidence_id]
    if not evidence:
        raise AppError(status_code=409, code="CHANGE_EVIDENCE_INVALID", message="请选择新旧知识中可核验的正式原文证据")
    return evidence


def _validate(db, change, new, old):
    if new.id == old.id or new.type != old.type:
        raise AppError(status_code=409, code="CHANGE_ENDPOINTS_INVALID", message="演化建议需要同类型的两个不同正式实体")
    if any(entity.status != "active" or entity.valid_to is not None for entity in (new, old)):
        raise AppError(status_code=409, code="CHANGE_STALE", message="知识已失效或状态已变化，请刷新后重新提出建议")
    effective = aware(change.effective_at)
    if effective > utc_now() or effective < max(aware(new.valid_from), aware(old.valid_from)):
        raise AppError(status_code=409, code="CHANGE_TIME_INVALID", message="生效时间须带时区，不早于两端知识有效起点且不晚于当前时间")
    if not valid_evidence(db, new) or not valid_evidence(db, old):
        raise AppError(status_code=409, code="CHANGE_EVIDENCE_INVALID", message="两端知识均须保留可核验的正式证据")
    _selected_evidence(db, change, new, old)
    if change.kind == "SUPERSEDES":
        # A strict linear chain: an active successor may replace just one predecessor.
        previous = db.scalar(select(KnowledgeChange.id).where(
            *_scope(new.user_id, new.project_id), KnowledgeChange.kind == "SUPERSEDES",
            KnowledgeChange.review_status == "confirmed", KnowledgeChange.new_entity_id == new.id,
        ).limit(1))
        if previous is not None:
            raise AppError(status_code=409, code="CHANGE_CHAIN_INVALID", message="新知识已有替代前驱；不支持分叉、合并或循环替代")


def read_change(db, change):
    new = _entity(db, change.user_id, change.project_id, change.new_entity_id)
    old = _entity(db, change.user_id, change.project_id, change.old_entity_id)
    evidence = [item for entity in (new, old) for item in valid_evidence(db, entity) if item.id == change.evidence_id]
    return ChangeRead(
        **{key: getattr(change, key) for key in ChangeRead.model_fields if key not in {"evidence", "new_entity_name", "old_entity_name"}},
        new_entity_name=new.name, old_entity_name=old.name, evidence=evidence,
    )


def create_change(db: Session, *, user_id, project_id, proposal: ChangeCreate):
    try:
        get_project(db, user_id=user_id, project_id=project_id)
        db.execute(select(Project.id).where(Project.id == project_id, Project.user_id == user_id).with_for_update())
        canonical = proposal.model_dump(mode="json")
        canonical["effective_at"] = proposal.effective_at.astimezone(timezone.utc).isoformat()
        fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        change_id = uuid.uuid5(project_id, f"{user_id}:knowledge-change-v1:{fingerprint}")
        existing = db.scalar(select(KnowledgeChange).where(*_scope(user_id, project_id), KnowledgeChange.id == change_id))
        if existing is not None:
            db.commit()
            return read_change(db, existing)
        change = KnowledgeChange(id=change_id, user_id=user_id, project_id=project_id, **proposal.model_dump(),
                                 review_status="pending", before={}, after={})
        new = _entity(db, user_id, project_id, change.new_entity_id)
        old = _entity(db, user_id, project_id, change.old_entity_id)
        _validate(db, change, new, old)
        db.add(change)
        db.commit()
        return read_change(db, change)
    except Exception:
        db.rollback()
        raise


def resolve_change(db: Session, *, user_id, project_id, change_id, action):
    try:
        get_project(db, user_id=user_id, project_id=project_id)
        db.execute(select(Project.id).where(Project.id == project_id, Project.user_id == user_id).with_for_update())
        change = db.scalar(select(KnowledgeChange).where(*_scope(user_id, project_id), KnowledgeChange.id == change_id)
                           .execution_options(populate_existing=True))
        if change is None:
            raise AppError(status_code=404, code="CHANGE_NOT_FOUND", message="演化建议不存在")
        target = "confirmed" if action == "confirm" else "rejected"
        if change.review_status != "pending":
            if change.review_status != target:
                raise AppError(status_code=409, code="CHANGE_ALREADY_RESOLVED", message="建议已处理，不支持撤回或改判")
            db.commit()
            return read_change(db, change)
        new = _entity(db, user_id, project_id, change.new_entity_id)
        old = _entity(db, user_id, project_id, change.old_entity_id)
        if action == "confirm":
            _validate(db, change, new, old)
        # All authoritative mutations remain in the graph service, under the project lock.
        graph.apply_reviewed_change(change, new, old, confirm=action == "confirm")
        db.commit()
        return read_change(db, change)
    except Exception:
        db.rollback()
        raise


def list_changes(db, *, user_id, project_id, review_status, page, page_size):
    get_project(db, user_id=user_id, project_id=project_id)
    query = select(KnowledgeChange).where(*_scope(user_id, project_id))
    if review_status:
        query = query.where(KnowledgeChange.review_status == review_status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(KnowledgeChange.created_at.desc(), KnowledgeChange.id)
                      .offset((page - 1) * page_size).limit(page_size))
    return ChangeList(items=[read_change(db, item) for item in items], total=total, page=page, page_size=page_size)


def history(db, *, user_id, project_id, entity_id):
    get_project(db, user_id=user_id, project_id=project_id)
    root = _entity(db, user_id, project_id, entity_id)
    entities, changes, frontier = {root.id: root}, {}, {root.id}
    truncated = False
    while frontier:
        rows = list(db.scalars(select(KnowledgeChange).where(
            *_scope(user_id, project_id), KnowledgeChange.kind == "SUPERSEDES", KnowledgeChange.review_status == "confirmed",
            or_(KnowledgeChange.new_entity_id.in_(frontier), KnowledgeChange.old_entity_id.in_(frontier)),
        ).order_by(KnowledgeChange.effective_at, KnowledgeChange.id).limit(MAX_HISTORY_CHANGES + 1)))
        truncated |= len(rows) > MAX_HISTORY_CHANGES
        next_frontier = set()
        for item in rows[:MAX_HISTORY_CHANGES]:
            if item.id in changes:
                continue
            needed = {item.new_entity_id, item.old_entity_id} - entities.keys()
            if len(entities) + len(needed) > MAX_HISTORY_ENTITIES or len(changes) >= MAX_HISTORY_CHANGES:
                truncated = True
                continue
            for endpoint in sorted(needed):
                entities[endpoint] = _entity(db, user_id, project_id, endpoint)
                next_frontier.add(endpoint)
            changes[item.id] = item
        frontier = next_frontier
    ordered_entities = sorted(entities.values(), key=lambda item: (aware(item.valid_from), str(item.id)))
    ordered_changes = sorted(changes.values(), key=lambda item: (aware(item.effective_at), str(item.id)))
    return EvolutionRead(entities=graph._reads(db, ordered_entities),
                         changes=[read_change(db, item) for item in ordered_changes], truncated=truncated)


def _normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def governance(db, *, user_id, project_id, limit):
    get_project(db, user_id=user_id, project_id=project_id)
    at = utc_now()
    entities = list(db.scalars(select(KnowledgeEntity).where(*graph.visible(KnowledgeEntity, user_id, project_id, at))
                              .order_by(KnowledgeEntity.created_at, KnowledgeEntity.id).limit(MAX_GOVERNANCE_ENTITIES + 1)))
    truncated = len(entities) > MAX_GOVERNANCE_ENTITIES
    entities = entities[:MAX_GOVERNANCE_ENTITIES]
    findings, names, summaries = [], {}, {}
    ids = [item.id for item in entities]
    by_id = {item.id: item for item in entities}
    contains_quote = (func.strpos(SourceChunk.content, KnowledgeEvidence.quote) if db.get_bind().dialect.name == "postgresql"
                      else func.instr(SourceChunk.content, KnowledgeEvidence.quote)) > 0
    evidenced = set(db.scalars(select(KnowledgeEvidence.entity_id).join(
        SourceChunk, SourceChunk.id == KnowledgeEvidence.chunk_id,
    ).join(SourceDocument, SourceDocument.id == KnowledgeEvidence.source_id).where(
        KnowledgeEvidence.entity_id.in_(ids), KnowledgeEvidence.user_id == user_id, KnowledgeEvidence.project_id == project_id,
        SourceChunk.user_id == user_id, SourceChunk.project_id == project_id,
        SourceChunk.source_id == KnowledgeEvidence.source_id,
        SourceDocument.user_id == user_id, SourceDocument.project_id == project_id,
        KnowledgeEvidence.quote != "", contains_quote,
    ).distinct()))
    edge_query = graph._edge_query(user_id, project_id, at)
    outgoing = edge_query.with_only_columns(KnowledgeRelationship.source_id).where(KnowledgeRelationship.source_id.in_(ids))
    incoming = edge_query.with_only_columns(KnowledgeRelationship.target_id).where(KnowledgeRelationship.target_id.in_(ids))
    connected = set(db.scalars(outgoing.union(incoming)))
    confirmed = select(KnowledgeChange).where(*_scope(user_id, project_id), KnowledgeChange.review_status == "confirmed")
    newer = confirmed.with_only_columns(KnowledgeChange.new_entity_id).where(KnowledgeChange.new_entity_id.in_(ids))
    older = confirmed.with_only_columns(KnowledgeChange.old_entity_id).where(KnowledgeChange.old_entity_id.in_(ids))
    connected.update(db.scalars(newer.union(older)))

    def add(kind, ids, message):
        key = f"governance-v1:{kind}:{':'.join(sorted(str(item) for item in ids))}"
        findings.append(GovernanceFinding(id=uuid.uuid5(project_id, key), kind=kind, entity_ids=ids, message=message,
            entities=[dict(id=item, name=by_id[item].name, summary=by_id[item].summary, type=by_id[item].type) for item in ids]))

    for entity in entities:
        if entity.id not in evidenced:
            add("missing_evidence", [entity.id], "未找到可核验的逐字原文证据；请人工核对，不自动删除知识。")
        key = entity.type, _normalized(entity.name)
        previous = names.get(key)
        summary_key = (*key, _normalized(entity.summary))
        duplicate = summaries.get(summary_key)
        if duplicate:
            add("duplicate", [duplicate.id, entity.id], "同类型、规范化名称与摘要相同，建议人工检查重复。")
        elif previous:
            add("possible_conflict", [previous.id, entity.id],
                "同类型同名但摘要不同，可能是补充、冲突或替代；这不是语义冲突判定。")
        names.setdefault(key, entity)
        summaries.setdefault(summary_key, entity)
        if entity.id not in connected:
            add("orphan", [entity.id], "当前没有可见语义关系或已确认演化关系，建议检查是否需要补充关联。")
    priority = {'missing_evidence': 0, 'duplicate': 1, 'possible_conflict': 2, 'orphan': 3}
    findings.sort(key=lambda finding: priority[finding.kind])
    return GovernanceRead(checked_at=at, scanned_entity_count=len(entities), findings=findings[:limit],
                          truncated=truncated or len(findings) > limit)
