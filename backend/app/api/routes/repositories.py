import uuid

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.core.config import get_settings
from app.schemas.repositories import (
    GithubRepositoryResolve,
    GithubRepositorySync,
    GithubRepositorySyncResult,
    RepositoryList,
    RepositoryRead,
    RepositoryResolve,
    RepositorySnapshotList,
    RepositorySnapshotRead,
)
from app.services import github_import, repositories as repository_service


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


@router.post(
    "/projects/{project_id}/repositories/resolve-github",
    response_model=RepositoryRead,
)
def resolve_github_repository(
    project_id: uuid.UUID,
    repository_in: GithubRepositoryResolve,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> RepositoryRead:
    return repository_service.resolve_github_repository(
        db,
        user_id=user_id,
        project_id=project_id,
        repository_in=repository_in,
    )


@router.post(
    "/projects/{project_id}/repositories/{repository_id}/sync-github",
    response_model=GithubRepositorySyncResult,
)
def sync_github_repository(
    project_id: uuid.UUID,
    repository_id: uuid.UUID,
    sync_in: GithubRepositorySync,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> GithubRepositorySyncResult:
    return github_import.sync_github_repository(
        db,
        settings=get_settings(),
        user_id=user_id,
        project_id=project_id,
        repository_id=repository_id,
        requested_ref=sync_in.ref,
    )


@router.get(
    "/projects/{project_id}/repositories/{repository_id}/snapshots",
    response_model=RepositorySnapshotList,
)
def list_repository_snapshots(
    project_id: uuid.UUID,
    repository_id: uuid.UUID,
    db: DatabaseSession,
    user_id: CurrentUserId,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> RepositorySnapshotList:
    items, total = github_import.list_repository_snapshots(
        db,
        user_id=user_id,
        project_id=project_id,
        repository_id=repository_id,
        page=page,
        page_size=page_size,
    )
    return RepositorySnapshotList(
        items=[RepositorySnapshotRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
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
