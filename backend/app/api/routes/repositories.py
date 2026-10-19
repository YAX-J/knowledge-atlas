import uuid

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.schemas.repositories import (
    RepositoryList,
    RepositoryRead,
    RepositoryResolve,
)
from app.services import repositories as repository_service


router = APIRouter(tags=["repositories"])


@router.post(
    "/projects/{project_id}/repositories/resolve",
    response_model=RepositoryRead,
)
def resolve_repository(
    project_id: uuid.UUID,
    repository_in: RepositoryResolve,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> RepositoryRead:
    return repository_service.resolve_repository(
        db,
        user_id=user_id,
        project_id=project_id,
        repository_in=repository_in,
    )


@router.get(
    "/projects/{project_id}/repositories",
    response_model=RepositoryList,
)
def list_repositories(
    project_id: uuid.UUID,
    db: DatabaseSession,
    user_id: CurrentUserId,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> RepositoryList:
    items, total = repository_service.list_repositories(
        db,
        user_id=user_id,
        project_id=project_id,
        page=page,
        page_size=page_size,
    )
    return RepositoryList(
        items=items, page=page, page_size=page_size, total=total
    )
