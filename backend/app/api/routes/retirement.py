import uuid

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.schemas.retirement import RetirementCreate, RetirementList, RetirementRead
from app.services import retirement

router = APIRouter(tags=['knowledge-lifecycle'])


@router.post('/projects/{project_id}/knowledge-retirements', response_model=RetirementRead)
def retire(project_id: uuid.UUID, request: RetirementCreate, db: DatabaseSession, user_id: CurrentUserId):
    return retirement.retire(db, user_id=user_id, project_id=project_id, request=request)


@router.get('/projects/{project_id}/knowledge-retirements', response_model=RetirementList)
def listing(project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
            page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
    return retirement.listing(db, user_id=user_id, project_id=project_id, page=page, page_size=page_size)
