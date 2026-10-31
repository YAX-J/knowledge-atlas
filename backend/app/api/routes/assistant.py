import uuid

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.core.config import get_settings
from app.schemas.assistant import AssistantList, AssistantRead, AssistantRequest
from app.services import project_assistant

router = APIRouter(tags=['project-assistant'])


@router.post('/projects/{project_id}/assistant/tasks', response_model=AssistantRead)
def start(project_id: uuid.UUID, request: AssistantRequest, db: DatabaseSession, user_id: CurrentUserId):
    return project_assistant.start_task(db, user_id=user_id, project_id=project_id, request=request, settings=get_settings())


@router.get('/projects/{project_id}/assistant/tasks', response_model=AssistantList)
def listing(project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
            page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1, le=50)):
    return project_assistant.list_tasks(db, user_id=user_id, project_id=project_id, page=page, page_size=page_size)


@router.get('/projects/{project_id}/assistant/tasks/{task_id}', response_model=AssistantRead)
def read(project_id: uuid.UUID, task_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId):
    return project_assistant.read_task(db, user_id=user_id, project_id=project_id, task_id=task_id)
