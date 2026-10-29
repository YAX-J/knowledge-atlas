"""Explicit, idempotent human identity and lifecycle operations under a project lock."""
import uuid

from sqlalchemy import func, select

from app.core.errors import AppError
from app.models.domain import Project, utc_now
from app.models.graph import KnowledgeEntity, KnowledgeRelationship
from app.models.evolution import KnowledgeChange
from app.models.workspace import EntityAlias, EntityMerge, KnowledgeOperation
from app.schemas.workspace import IdentityRead, OperationList, OperationRead
from app.services import graph, identities
from app.services.evolution import aware, valid_evidence
from app.services.projects import get_project


def _fail(code, message):
    raise AppError(status_code=409, code=code, message=message)


def snapshot(record):
    return dict(id=str(record.id), name=record.name, status=record.status,
                valid_from=aware(record.valid_from).isoformat(),
                valid_to=aware(record.valid_to).isoformat() if record.valid_to else None)


def operate(db, *, user_id, project_id, request):
    try:
        get_project(db, user_id=user_id, project_id=project_id)
        db.execute(select(Project.id).where(Project.id == project_id, Project.user_id == user_id).with_for_update())
        payload = request.model_dump(mode='json', exclude={'request_id'})
        operation_id = uuid.uuid5(project_id, f'{user_id}:knowledge-operation-v1:{request.request_id}')
        existing = db.get(KnowledgeOperation, operation_id, populate_existing=True)
        if existing:
            if existing.payload != payload:
                _fail('OPERATION_REQUEST_CONFLICT', '此提交标识已用于不同操作')
            db.commit()
            return OperationRead.model_validate(existing)
        if request.action == 'reverse_change':
            return _reverse_change(db, user_id, project_id, request, operation_id, payload)
        model = KnowledgeEntity if request.kind == 'entity' else KnowledgeRelationship
        record = db.scalar(select(model).where(model.id == request.knowledge_id, model.user_id == user_id,
            model.project_id == project_id).execution_options(populate_existing=True))
        if record is None:
            raise AppError(status_code=404, code='KNOWLEDGE_NOT_FOUND', message='知识不存在或不属于此项目')
        now = utc_now()
        before, after = snapshot(record), {}
        current = db.scalar(select(model.id).where(model.id == record.id, *graph.visible(model, user_id, project_id, now))) is not None
        if request.action in {'alias', 'merge'} and request.kind != 'entity':
            _fail('IDENTITY_ENTITY_REQUIRED', '别名和合并只适用于实体')
        if request.action == 'alias':
            if not current or not request.alias:
                _fail('ALIAS_INVALID', '请选择当前实体并填写别名')
            name = identities.normalized(request.alias)
            other = db.scalar(select(EntityAlias).where(EntityAlias.user_id == user_id, EntityAlias.project_id == project_id,
                EntityAlias.entity_type == record.type, EntityAlias.normalized_name == name))
            names = db.execute(select(KnowledgeEntity.id, KnowledgeEntity.name).where(KnowledgeEntity.user_id == user_id,
                KnowledgeEntity.project_id == project_id, KnowledgeEntity.type == record.type,
                KnowledgeEntity.id != record.id, *graph.visible(KnowledgeEntity, user_id, project_id, now)))
            collision = any(identities.normalized(value) == name for _, value in names)
            links = identities.mapping(db, user_id, project_id, now)
            if collision or (other and links.get(other.entity_id, other.entity_id) != record.id):
                _fail('ALIAS_AMBIGUOUS', '别名已指向另一实体，请先核对并合并身份')
            if other is None:
                db.add(EntityAlias(user_id=user_id, project_id=project_id, entity_id=record.id,
                    entity_type=record.type, name=request.alias, normalized_name=name, reason=request.reason))
            after = dict(entity_id=str(record.id), alias=request.alias)
        elif request.action == 'merge':
            target = db.scalar(select(KnowledgeEntity).where(KnowledgeEntity.id == request.target_id,
                *graph.visible(KnowledgeEntity, user_id, project_id, now)))
            if not current or target is None or target.id == record.id or target.type != record.type:
                _fail('MERGE_ENDPOINTS_INVALID', '请选择同类型的两个不同当前实体')
            if not valid_evidence(db, record) or not valid_evidence(db, target):
                _fail('MERGE_EVIDENCE_INVALID', '合并双方均须保留可核验原文')
            if any(len(identities.normalized(item.name))>255 for item in (record,target)):
                _fail('MERGE_ALIAS_TOO_LONG', '实体名称规范化后超过 255 字符，请核对名称并通过正常审核修正后再合并')
            members = list(db.scalars(select(EntityMerge).where(*identities.active_merge(user_id, project_id, now),
                EntityMerge.target_id == record.id)))
            target_members = db.scalar(select(func.count()).select_from(EntityMerge).where(
                *identities.active_merge(user_id, project_id, now), EntityMerge.target_id == target.id)) or 0
            if len(members) + target_members + 1 > 1000:
                _fail('MERGE_LIMIT', '单个身份最多合并 1000 个成员')
            for item in members:
                item.valid_to = now
            sources = [record.id, *(item.source_id for item in members)]
            for source_id in sources:
                db.add(EntityMerge(user_id=user_id, project_id=project_id, source_id=source_id,
                    target_id=target.id, valid_from=now))
            # Keep names as searchable aliases without changing either original record.
            for entity in [record, target]:
                norm = identities.normalized(entity.name)
                alias = db.scalar(select(EntityAlias).where(EntityAlias.user_id == user_id,
                    EntityAlias.project_id == project_id, EntityAlias.entity_type == entity.type,
                    EntityAlias.normalized_name == norm))
                if alias is None:
                    db.add(EntityAlias(user_id=user_id, project_id=project_id, entity_id=entity.id,
                        entity_type=entity.type, name=entity.name, normalized_name=norm, reason=request.reason))
            after = dict(canonical_id=str(target.id), member_ids=[str(item) for item in sources], effective_at=now.isoformat())
        elif request.action == 'unmerge':
            links = list(db.scalars(select(EntityMerge).where(*identities.active_merge(user_id, project_id, now),
                EntityMerge.source_id == record.id)))
            if not links:
                _fail('MERGE_NOT_CURRENT', '此实体当前没有合并身份')
            for item in links:
                item.valid_to = now
            after = dict(canonical_id=str(record.id), effective_at=now.isoformat())
        else:
            graph.apply_lifecycle(db, record, request, now, current=current)
            after = snapshot(record)
        event = KnowledgeOperation(id=operation_id, user_id=user_id, project_id=project_id,
            action=request.action, reason=request.reason, payload=payload, before=before, after=after)
        db.add(event)
        db.commit()
        return OperationRead.model_validate(event)
    except Exception:
        db.rollback()
        raise


def _reverse_change(db, user_id, project_id, request, operation_id, payload):
    change = db.scalar(select(KnowledgeChange).where(KnowledgeChange.id == request.knowledge_id,
        KnowledgeChange.user_id == user_id, KnowledgeChange.project_id == project_id,
        KnowledgeChange.review_status == 'confirmed', KnowledgeChange.kind == 'SUPERSEDES'))
    if change is None:
        _fail('CHANGE_NOT_REVERSIBLE', '请选择已确认的替代记录')
    new = db.get(KnowledgeEntity, change.new_entity_id, populate_existing=True)
    old = db.get(KnowledgeEntity, change.old_entity_id, populate_existing=True)
    now = utc_now()
    dependencies = db.scalar(select(KnowledgeChange.id).where(KnowledgeChange.user_id == user_id,
        KnowledgeChange.project_id == project_id, KnowledgeChange.review_status == 'confirmed',
        KnowledgeChange.kind == 'SUPERSEDES', KnowledgeChange.id != change.id,
        KnowledgeChange.effective_at >= change.effective_at,
        (KnowledgeChange.new_entity_id.in_([old.id, new.id]) | KnowledgeChange.old_entity_id.in_([old.id, new.id]))).limit(1))
    dependencies = dependencies or db.scalar(select(EntityMerge.id).where(*identities.active_merge(user_id,project_id,now),
        (EntityMerge.source_id.in_([old.id,new.id]) | EntityMerge.target_id.in_([old.id,new.id]))).limit(1))
    if dependencies or old.valid_to is None or aware(old.valid_to) != aware(change.effective_at) or new.valid_to is not None:
        _fail('CHANGE_HAS_DEPENDENCIES', '替代已有后续依赖或状态变化，不能单独撤销；请逐项核对生命周期')
    before = dict(old=snapshot(old), new=snapshot(new), change_id=str(change.id))
    if not valid_evidence(db, old) or not valid_evidence(db, new):
        _fail('CHANGE_EVIDENCE_INVALID', '撤销需要两端原始证据')
    graph.apply_lifecycle(db, old, request.model_copy(update={'action':'reactivate','kind':'entity'}), now, current=False)
    graph.apply_lifecycle(db, new, request.model_copy(update={'action':'withdraw','kind':'entity'}), now, current=True)
    event = KnowledgeOperation(id=operation_id, user_id=user_id, project_id=project_id, action=request.action,
        reason=request.reason, payload=payload, before=before, after=dict(old=snapshot(old),new=snapshot(new)))
    db.add(event)
    db.commit()
    return OperationRead.model_validate(event)


def evolution_group(db, *, user_id, project_id, request):
    try:
        get_project(db, user_id=user_id, project_id=project_id)
        db.execute(select(Project.id).where(Project.id == project_id, Project.user_id == user_id).with_for_update())
        payload = request.model_dump(mode='json', exclude={'request_id'})
        event_id = uuid.uuid5(project_id, f'{user_id}:evolution-group-v1:{request.request_id}')
        event = db.get(KnowledgeOperation, event_id, populate_existing=True)
        if event:
            if event.payload != payload:
                _fail('OPERATION_REQUEST_CONFLICT', '此提交标识已用于不同操作')
            db.commit()
            return OperationRead.model_validate(event)
        old_ids, new_ids = set(request.old_entity_ids), set(request.new_entity_ids)
        if len(old_ids) != len(request.old_entity_ids) or len(new_ids) != len(request.new_entity_ids) or old_ids & new_ids:
            _fail('CHANGE_GROUP_INVALID', '新旧知识列表不得重复或交叉')
        now = utc_now()
        records = {item.id:item for item in db.scalars(select(KnowledgeEntity).where(
            KnowledgeEntity.id.in_(old_ids | new_ids), *graph.visible(KnowledgeEntity,user_id,project_id,now))
            .execution_options(populate_existing=True))}
        if set(records) != old_ids | new_ids or len({item.type for item in records.values()}) != 1:
            _fail('CHANGE_GROUP_INVALID', '分叉或合并需要同项目、同类型的当前有效知识')
        evidence = {key:valid_evidence(db,item) for key,item in records.items()}
        if not all(evidence.values()):
            _fail('CHANGE_EVIDENCE_INVALID', '每项新旧知识都需要可核验原文')
        rows = list(db.execute(select(KnowledgeChange.new_entity_id,KnowledgeChange.old_entity_id).where(
            KnowledgeChange.user_id==user_id,KnowledgeChange.project_id==project_id,
            KnowledgeChange.kind=='SUPERSEDES',KnowledgeChange.review_status=='confirmed').limit(5001)))
        if len(rows)>5000:
            _fail('CHANGE_HISTORY_LIMIT', '替代历史超过安全检查上限，请缩小项目')
        adjacency={}
        for source,target in rows:
            adjacency.setdefault(source,set()).add(target)
        for source in new_ids:
            adjacency.setdefault(source,set()).update(old_ids)
        # Iterative topological check also handles long valid histories without recursion limits.
        vertices=set(adjacency) | {value for values in adjacency.values() for value in values}
        indegree={key:0 for key in vertices}
        for values in adjacency.values():
            for key in values:
                indegree[key]+=1
        ready=[key for key,value in indegree.items() if value==0]
        visited=0
        while ready:
            node=ready.pop();visited+=1
            for key in adjacency.get(node,()):
                indegree[key]-=1
                if indegree[key]==0:
                    ready.append(key)
        if visited!=len(vertices):
            _fail('CHANGE_CYCLE', '替代会形成循环，操作已拒绝')
        before={str(key):snapshot(item) for key,item in records.items()}
        changes=[]
        for new_id in sorted(new_ids):
            for old_id in sorted(old_ids):
                change=KnowledgeChange(id=uuid.uuid5(event_id,f'{new_id}:{old_id}'),user_id=user_id,project_id=project_id,
                    new_entity_id=new_id,old_entity_id=old_id,evidence_id=evidence[new_id][0].id,
                    kind='SUPERSEDES',reason=request.reason,effective_at=now,review_status='confirmed',resolved_at=now,
                    before={'new':snapshot(records[new_id]),'old':snapshot(records[old_id])},after={})
                changes.append(change)
        graph.apply_evolution_group(records, old_ids, now)
        for change in changes:
            change.after={'new':snapshot(records[change.new_entity_id]),'old':snapshot(records[change.old_entity_id])}
            db.add(change)
        event=KnowledgeOperation(id=event_id,user_id=user_id,project_id=project_id,action='evolution_group',reason=request.reason,
            payload=payload,before=before,after={str(key):snapshot(item) for key,item in records.items()})
        db.add(event)
        db.commit()
        return OperationRead.model_validate(event)
    except Exception:
        db.rollback()
        raise


def identity(db, *, user_id, project_id, entity_id, valid_at=None):
    get_project(db, user_id=user_id, project_id=project_id)
    entity = db.scalar(select(KnowledgeEntity).where(KnowledgeEntity.id == entity_id,
        KnowledgeEntity.user_id == user_id, KnowledgeEntity.project_id == project_id))
    if entity is None:
        raise AppError(status_code=404, code='KNOWLEDGE_NOT_FOUND', message='知识不存在')
    at = valid_at or utc_now()
    links = identities.mapping(db, user_id, project_id, at)
    target = links.get(entity_id, entity_id)
    aliases = identities.alias_names(db, user_id, project_id, at, [target])
    return IdentityRead(entity_id=entity_id, canonical_id=target, aliases=sorted(set(aliases.get(target, []))),
        member_ids=sorted([target, *(source for source, destination in links.items() if destination == target)]))


def operations(db, *, user_id, project_id, page, page_size):
    get_project(db, user_id=user_id, project_id=project_id)
    query = select(KnowledgeOperation).where(KnowledgeOperation.user_id == user_id,
        KnowledgeOperation.project_id == project_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    return OperationList(items=[OperationRead.model_validate(item) for item in db.scalars(query.order_by(
        KnowledgeOperation.created_at.desc(), KnowledgeOperation.id).offset((page - 1) * page_size).limit(page_size))],
        total=total, page=page, page_size=page_size)
