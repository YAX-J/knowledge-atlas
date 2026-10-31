import uuid

from fastapi import APIRouter, Query, Response

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.core.config import get_settings
from app.schemas.assistant import AssistantContinue, AssistantEvents, AssistantList, AssistantRead, AssistantRequest, AssistantResult
from app.schemas.assistant_operations import ApprovalRequest, SaveArtifact
from app.schemas.notes import NoteRead
from app.services import assistant_operations
from app.services import project_assistant
from app.services import assistant_execution

router = APIRouter(tags=['project-assistant'])


@router.post('/projects/{project_id}/assistant/tasks', response_model=AssistantRead,
             responses={202:{'model':AssistantRead,'description':'Queued async-v2 task; no provider calls'}})
def start(project_id: uuid.UUID, request: AssistantRequest, response: Response, db: DatabaseSession, user_id: CurrentUserId):
    if request.protocol in {'assistant-task-v2','assistant-task-v3'}:response.status_code=202
    return project_assistant.start_task(db, user_id=user_id, project_id=project_id, request=request, settings=get_settings())


@router.get('/projects/{project_id}/assistant/tasks', response_model=AssistantList)
def listing(project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
            page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1, le=50)):
    return project_assistant.list_tasks(db, user_id=user_id, project_id=project_id, page=page, page_size=page_size)


@router.get('/projects/{project_id}/assistant/tasks/{task_id}', response_model=AssistantRead)
def read(project_id: uuid.UUID, task_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId):
    return project_assistant.read_task(db, user_id=user_id, project_id=project_id, task_id=task_id)


@router.post('/projects/{project_id}/assistant/tasks/{task_id}/cancel',response_model=AssistantRead)
def cancel(project_id:uuid.UUID,task_id:uuid.UUID,db:DatabaseSession,user_id:CurrentUserId):
    return assistant_execution.cancel(db,user_id=user_id,project_id=project_id,task_id=task_id)


@router.post('/projects/{project_id}/assistant/tasks/{task_id}/continue',response_model=AssistantRead,status_code=202)
def resume(project_id:uuid.UUID,task_id:uuid.UUID,request:AssistantContinue,db:DatabaseSession,user_id:CurrentUserId):
    return assistant_execution.continue_task(db,user_id=user_id,project_id=project_id,task_id=task_id,request=request)


@router.get('/projects/{project_id}/assistant/tasks/{task_id}/events',response_model=AssistantEvents)
def events(project_id:uuid.UUID,task_id:uuid.UUID,db:DatabaseSession,user_id:CurrentUserId,
           after:int=Query(default=0,ge=0),limit:int=Query(default=100,ge=1,le=100)):
    task=project_assistant.read_task(db,user_id=user_id,project_id=project_id,task_id=task_id)
    rows=[e for e in task.events if e.sequence>after]
    return AssistantEvents(items=rows[:limit],next_sequence=rows[min(limit,len(rows))-1].sequence if rows else after,has_more=len(rows)>limit)


@router.get('/projects/{project_id}/assistant/tasks/{task_id}/artifacts/{artifact_id}',response_model=AssistantResult)
def artifact(project_id:uuid.UUID,task_id:uuid.UUID,artifact_id:uuid.UUID,db:DatabaseSession,user_id:CurrentUserId):
    return assistant_execution.read_artifact(db,user_id=user_id,project_id=project_id,task_id=task_id,artifact_id=artifact_id)

@router.post('/projects/{project_id}/assistant/tasks/{task_id}/approvals',response_model=AssistantRead)
def approve(project_id:uuid.UUID,task_id:uuid.UUID,request:ApprovalRequest,db:DatabaseSession,user_id:CurrentUserId):
    assistant_operations.approve(db,user_id=user_id,project_id=project_id,task_id=task_id,request=request)
    return project_assistant.read_task(db,user_id=user_id,project_id=project_id,task_id=task_id)

@router.post('/projects/{project_id}/assistant/tasks/{task_id}/artifacts/{artifact_id}/note',response_model=NoteRead)
def save_note(project_id:uuid.UUID,task_id:uuid.UUID,artifact_id:uuid.UUID,request:SaveArtifact,db:DatabaseSession,user_id:CurrentUserId):
    return assistant_operations.save_artifact(db,user_id=user_id,project_id=project_id,task_id=task_id,artifact_id=artifact_id,request=request)
