import uuid

from fastapi import APIRouter, Query, status

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.schemas.projects import ProjectArchive, ProjectCreate, ProjectEdit, ProjectList, ProjectRead
from app.services import projects as project_service


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    project_in: ProjectCreate,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> ProjectRead:
    return project_service.create_project(db, user_id=user_id, project_in=project_in)


@router.get("", response_model=ProjectList)
def list_projects(
    db: DatabaseSession,
    user_id: CurrentUserId,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    archived: bool = False,
) -> ProjectList:
    projects, total = project_service.list_projects(
        db, user_id=user_id, page=page, page_size=page_size, archived=archived,
    )
    return ProjectList(items=projects, page=page, page_size=page_size, total=total)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: uuid.UUID,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> ProjectRead:
    return project_service.get_project(db, user_id=user_id, project_id=project_id)


@router.put('/{project_id}', response_model=ProjectRead)
def edit_project(project_id: uuid.UUID, request: ProjectEdit, db: DatabaseSession, user_id: CurrentUserId):
    return project_service.edit_project(db, user_id=user_id, project_id=project_id, request=request)


@router.put('/{project_id}/archive', response_model=ProjectRead)
def archive_project(project_id: uuid.UUID, request: ProjectArchive, db: DatabaseSession, user_id: CurrentUserId):
    return project_service.archive_project(db, user_id=user_id, project_id=project_id, request=request)

