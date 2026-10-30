import uuid
from fastapi import APIRouter, Query
from app.api.dependencies import CurrentUserId, DatabaseSession
from app.core.config import get_settings
from app.services import agent_workflows
from app.workflows.contracts import WorkflowList, WorkflowRead, WorkflowRequest, WorkflowSummaryList

router=APIRouter(tags=['agent-workflows'])


@router.post('/projects/{project_id}/agent-runs',response_model=WorkflowRead)
def start(project_id:uuid.UUID,request:WorkflowRequest,db:DatabaseSession,user_id:CurrentUserId):
    return agent_workflows.start_run(db,user_id=user_id,project_id=project_id,request=request,settings=get_settings())


@router.get('/projects/{project_id}/agent-runs',response_model=WorkflowList|WorkflowSummaryList)
def listing(project_id:uuid.UUID,db:DatabaseSession,user_id:CurrentUserId,page:int=Query(default=1,ge=1),page_size:int=Query(default=10,ge=1,le=50),summary:bool=False):
    return agent_workflows.list_runs(db,user_id=user_id,project_id=project_id,page=page,page_size=page_size,summary=summary)


@router.get('/projects/{project_id}/agent-runs/{run_id}',response_model=WorkflowRead)
def read(project_id:uuid.UUID,run_id:uuid.UUID,db:DatabaseSession,user_id:CurrentUserId):
    return agent_workflows.read_run(db,user_id=user_id,project_id=project_id,run_id=run_id)


@router.post('/projects/{project_id}/agent-runs/{run_id}/resume',response_model=WorkflowRead)
def resume(project_id:uuid.UUID,run_id:uuid.UUID,db:DatabaseSession,user_id:CurrentUserId):
    return agent_workflows.resume_run(db,user_id=user_id,project_id=project_id,run_id=run_id)
