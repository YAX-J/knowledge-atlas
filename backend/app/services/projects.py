import uuid
from datetime import timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.domain import Project, utc_now
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
    db: Session, *, user_id: uuid.UUID, page: int, page_size: int, archived: bool = False,
) -> tuple[list[Project], int]:
    filters = (Project.user_id == user_id, Project.archived_at.is_not(None) if archived else Project.archived_at.is_(None))
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


def _check_revision(project, expected):
    actual = project.updated_at
    if actual.tzinfo is None:
        actual = actual.replace(tzinfo=timezone.utc)
    if actual != expected:
        raise AppError(status_code=409, code='PROJECT_CHANGED', message='项目已变化，请刷新后重新修改')


def edit_project(db, *, user_id, project_id, request):
    project = get_project(db, user_id=user_id, project_id=project_id, lock=True)
    if (project.name, project.description) == (request.name.strip(), request.description.strip()):
        db.commit()
        return project
    _check_revision(project, request.expected_updated_at)
    project.name, project.description = request.name.strip(), request.description.strip()
    project.updated_at = utc_now()
    db.commit(); db.refresh(project)
    return project


def archive_project(db, *, user_id, project_id, request):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user_id).with_for_update())
    if project is None:
        raise AppError(status_code=404, code='PROJECT_NOT_FOUND', message='项目不存在')
    if (project.archived_at is not None) == request.archived:
        db.commit()
        return project
    _check_revision(project, request.expected_updated_at)
    if request.archived:
        from app.models.assistant_task import AssistantTask
        from app.models.agent_run import AgentRun
        from app.models.workspace import Conversation
        conditions = [
            (AssistantTask, AssistantTask.status.in_(['queued','running','waiting_approval'])),
            (AgentRun, or_(AgentRun.status == 'awaiting_review', and_(AgentRun.status == 'running',
                or_(AgentRun.lease_until.is_(None), AgentRun.lease_until > utc_now())))),
        ]
        for model, active in conditions:
            if db.scalar(select(model.id).where(model.user_id == user_id, model.project_id == project_id,
                    active).limit(1)) is not None:
                raise AppError(status_code=409, code='PROJECT_BUSY', message='项目仍有执行或待审批任务，请先完成或取消')
        if db.scalar(select(Conversation.id).where(Conversation.user_id == user_id,
                Conversation.project_id == project_id, Conversation.active_request_id.is_not(None),
                Conversation.lease_until > utc_now()).limit(1)) is not None:
            raise AppError(status_code=409, code='PROJECT_BUSY', message='项目仍有会话正在回答，请等待完成')
    project.archived_at = utc_now() if request.archived else None
    project.updated_at = utc_now()
    db.commit(); db.refresh(project)
    return project

