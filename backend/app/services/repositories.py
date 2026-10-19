import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.domain import Project, SourceRepository
from app.schemas.repositories import RepositoryResolve
from app.services.projects import get_project


def resolve_repository(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    repository_in: RepositoryResolve,
) -> SourceRepository:
    get_project(db, user_id=user_id, project_id=project_id)
    db.execute(
        select(Project.id)
        .where(Project.id == project_id, Project.user_id == user_id)
        .with_for_update()
    )
    repository = db.scalar(select(SourceRepository).where(
        SourceRepository.user_id == user_id,
        SourceRepository.project_id == project_id,
        SourceRepository.kind == repository_in.kind,
        SourceRepository.name == repository_in.name,
    ))
    if repository is None:
        repository = SourceRepository(
            user_id=user_id,
            project_id=project_id,
            name=repository_in.name,
            kind=repository_in.kind,
        )
        db.add(repository)
    db.commit()
    db.refresh(repository)
    return repository


def get_repository(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    repository_id: uuid.UUID,
) -> SourceRepository:
    repository = db.scalar(select(SourceRepository).where(
        SourceRepository.id == repository_id,
        SourceRepository.user_id == user_id,
        SourceRepository.project_id == project_id,
    ))
    if repository is None:
        raise AppError(
            status_code=404,
            code="SOURCE_REPOSITORY_NOT_FOUND",
            message="代码仓库不存在",
            details={"repository_id": str(repository_id)},
        )
    return repository


def list_repositories(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[SourceRepository], int]:
    get_project(db, user_id=user_id, project_id=project_id)
    filters = (
        SourceRepository.user_id == user_id,
        SourceRepository.project_id == project_id,
    )
    total = db.scalar(
        select(func.count()).select_from(SourceRepository).where(*filters)
    ) or 0
    items = list(db.scalars(
        select(SourceRepository)
        .where(*filters)
        .order_by(SourceRepository.created_at.desc(), SourceRepository.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ))
    return items, total
