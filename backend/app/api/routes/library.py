import uuid

from fastapi import APIRouter

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.schemas.library import ArchiveRequest, FeedbackCreate, FeedbackRead, SourceArchiveRead
from app.services import library

router = APIRouter(tags=['library'])


@router.put('/projects/{project_id}/sources/{source_id}/archive', response_model=SourceArchiveRead)
def archive_source(project_id: uuid.UUID, source_id: uuid.UUID, request: ArchiveRequest,
                   db: DatabaseSession, user_id: CurrentUserId):
    return library.archive_source(db, user_id=user_id, project_id=project_id, source_id=source_id, request=request)


@router.get('/projects/{project_id}/answers/{turn_id}/feedback', response_model=list[FeedbackRead])
def feedback(project_id: uuid.UUID, turn_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId):
    return library.list_feedback(db, user_id=user_id, project_id=project_id, turn_id=turn_id)


@router.post('/projects/{project_id}/answers/{turn_id}/feedback', response_model=FeedbackRead, status_code=201)
def create_feedback(project_id: uuid.UUID, turn_id: uuid.UUID, request: FeedbackCreate,
                    db: DatabaseSession, user_id: CurrentUserId):
    return library.create_feedback(db, user_id=user_id, project_id=project_id, turn_id=turn_id, request=request)
