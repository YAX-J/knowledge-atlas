"""Explicit retirement closes the current interval, preserving historical evidence."""
import uuid

from sqlalchemy import func, select

from app.core.errors import AppError
from app.models.domain import Project, utc_now
from app.models.graph import KnowledgeEntity, KnowledgeRelationship
from app.models.retirement import KnowledgeRetirement
from app.schemas.retirement import RetirementList, RetirementRead
from app.services import graph
from app.services.evolution import aware
from app.services.projects import get_project


def read(event):
    return RetirementRead(id=event.id, project_id=event.project_id,
        kind='entity' if event.entity_id else 'relationship', knowledge_id=event.entity_id or event.relationship_id,
        name=event.before['name'], category=event.category, reason=event.reason,
        effective_at=aware(event.effective_at), before=event.before, after=event.after)


def retire(db, *, user_id, project_id, request):
    try:
        get_project(db, user_id=user_id, project_id=project_id)
        db.execute(select(Project.id).where(Project.id == project_id, Project.user_id == user_id).with_for_update())
        event_id = uuid.uuid5(project_id, f'{user_id}:knowledge-retirement-v1:{request.request_id}')
        event = db.get(KnowledgeRetirement, event_id, populate_existing=True)
        if event is not None:
            result = read(event)
            if (result.kind, result.knowledge_id, result.category, result.reason) != (
                    request.kind, request.knowledge_id, request.category, request.reason):
                raise AppError(status_code=409, code='RETIREMENT_REQUEST_CONFLICT', message='此提交标识已用于不同操作，请刷新记录')
            db.commit()
            return result
        model = KnowledgeEntity if request.kind == 'entity' else KnowledgeRelationship
        record = db.scalar(select(model).where(model.id == request.knowledge_id,
            model.user_id == user_id, model.project_id == project_id).execution_options(populate_existing=True))
        if record is None:
            raise AppError(status_code=404, code='KNOWLEDGE_NOT_FOUND', message='知识不存在或不属于此项目')
        now = utc_now()
        if record.status != 'active' or record.valid_to is not None or aware(record.valid_from) >= now:
            raise AppError(status_code=409, code='KNOWLEDGE_NOT_CURRENT', message='知识已失效或状态已变化，请刷新记录')
        if request.kind == 'relationship' and db.scalar(graph._edge_query(user_id, project_id, now).where(model.id == record.id)) is None:
            raise AppError(status_code=409, code='KNOWLEDGE_NOT_CURRENT', message='关系端点已失效，请先核对知识记录')
        event = KnowledgeRetirement(id=event_id, user_id=user_id, project_id=project_id,
            entity_id=record.id if request.kind == 'entity' else None,
            relationship_id=record.id if request.kind == 'relationship' else None,
            category=request.category, reason=request.reason, effective_at=now)
        # Graph service owns the only new authoritative validity mutation boundary.
        graph.apply_retirement(record, event)
        db.add(event)
        db.commit()
        return read(event)
    except Exception:
        db.rollback()
        raise


def listing(db, *, user_id, project_id, page, page_size):
    get_project(db, user_id=user_id, project_id=project_id)
    query = select(KnowledgeRetirement).where(KnowledgeRetirement.user_id == user_id,
        KnowledgeRetirement.project_id == project_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    events = db.scalars(query.order_by(KnowledgeRetirement.effective_at.desc(), KnowledgeRetirement.id)
        .offset((page - 1) * page_size).limit(page_size))
    return RetirementList(items=[read(event) for event in events], total=total, page=page, page_size=page_size)
