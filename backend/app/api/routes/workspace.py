import uuid
from fastapi import APIRouter, Query
from pydantic import AwareDatetime
from app.api.dependencies import CurrentUserId, DatabaseSession
from app.schemas.workspace import EvolutionGroupCreate, IdentityRead, OperationCreate, OperationList, OperationRead
from app.services import workspace
from sqlalchemy import func, select
from app.models.domain import CandidateKnowledge, SourceDocument, ProcessingTask, utc_now
from app.models.graph import KnowledgeEntity
from app.services import graph
from app.services.projects import get_project

router = APIRouter(tags=['knowledge-identity'])


@router.get('/projects/{project_id}/overview')
def overview(project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId):
    get_project(db,user_id=user_id,project_id=project_id)
    def count(model,*extra):
        return select(func.count()).select_from(model).where(model.user_id==user_id,model.project_id==project_id,*extra).scalar_subquery()
    now=utc_now()
    row=db.execute(select(
        count(SourceDocument).label('sources'),count(SourceDocument,SourceDocument.status=='ready').label('ready_sources'),
        count(CandidateKnowledge,CandidateKnowledge.review_status=='pending').label('pending_reviews'),
        count(KnowledgeEntity,*graph.visible(KnowledgeEntity,user_id,project_id,now)).label('entities'),
        select(func.count()).select_from(graph._edge_query(user_id,project_id,now).subquery()).scalar_subquery().label('relationships'),
        count(ProcessingTask,ProcessingTask.status.in_(['queued','running'])).label('pending_tasks'))).mappings().one()
    return dict(project_id=project_id,**dict(row))


@router.post('/projects/{project_id}/knowledge-change-groups', response_model=OperationRead)
def evolution_group(project_id: uuid.UUID, request: EvolutionGroupCreate, db: DatabaseSession, user_id: CurrentUserId):
    return workspace.evolution_group(db,user_id=user_id,project_id=project_id,request=request)


@router.post('/projects/{project_id}/knowledge-operations', response_model=OperationRead)
def operate(project_id: uuid.UUID, request: OperationCreate, db: DatabaseSession, user_id: CurrentUserId):
    return workspace.operate(db, user_id=user_id, project_id=project_id, request=request)


@router.get('/projects/{project_id}/knowledge-operations', response_model=OperationList)
def listing(project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
            page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return workspace.operations(db, user_id=user_id, project_id=project_id, page=page, page_size=page_size)


@router.get('/projects/{project_id}/knowledge/entities/{entity_id}/identity', response_model=IdentityRead)
def identity(project_id: uuid.UUID, entity_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
             valid_at: AwareDatetime | None = None):
    return workspace.identity(db, user_id=user_id, project_id=project_id, entity_id=entity_id, valid_at=valid_at)
