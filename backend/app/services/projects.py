import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.domain import Project
from app.schemas.projects import ProjectCreate


def create_project(
    db: Session, *, user_id: uuid.UUID, project_in: ProjectCreate
) -> Project:
    project = Project(
        user_id=user_id,
        name=project_in.name.strip(),
        description=project_in.description.strip(),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_projects(
    db: Session, *, user_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[Project], int]:
    filters = (Project.user_id == user_id, Project.archived_at.is_(None))
    total = db.scalar(select(func.count()).select_from(Project).where(*filters)) or 0
    projects = list(
        db.scalars(
            select(Project)
            .where(*filters)
            .order_by(Project.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return projects, total


def get_project(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, lock: bool = False,
) -> Project:
    query = select(Project).where(
        Project.id == project_id,
        Project.user_id == user_id,
        Project.archived_at.is_(None),
    )
    project = db.scalar(query.with_for_update() if lock else query)
    if project is None:
        raise AppError(
            status_code=404,
            code="PROJECT_NOT_FOUND",
            message="项目不存在",
            details={"project_id": str(project_id)},
        )
    return project

