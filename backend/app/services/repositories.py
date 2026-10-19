import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.domain import Project, SourceRepository
from app.schemas.repositories import GithubRepositoryResolve, RepositoryResolve
from app.services.projects import get_project


GITHUB_REMOTE_PATTERNS = (
    re.compile(
        r"^https://github\.com/(?P<owner>[^/\s]+)/(?P<name>[^/\s]+?)(?:\.git)?/?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^git@github\.com:(?P<owner>[^/\s]+)/(?P<name>[^/\s]+?)(?:\.git)?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^ssh://git@github\.com/(?P<owner>[^/\s]+)/(?P<name>[^/\s]+?)(?:\.git)?/?$",
        re.IGNORECASE,
    ),
)
GITHUB_OWNER = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,37}[a-z0-9])?$")
GITHUB_REPOSITORY_NAME = re.compile(r"^[a-z0-9._-]{1,100}$")


def normalize_github_remote(remote_url: str) -> tuple[str, str, str]:
    for pattern in GITHUB_REMOTE_PATTERNS:
        match = pattern.fullmatch(remote_url)
        if match is None:
            continue
        owner = match.group("owner").lower()
        name = match.group("name").lower()
        if (
            owner not in {".", ".."}
            and name not in {".", ".."}
            and GITHUB_OWNER.fullmatch(owner)
            and GITHUB_REPOSITORY_NAME.fullmatch(name)
        ):
            return owner, name, f"https://github.com/{owner}/{name}"
    raise AppError(
        status_code=422,
        code="GITHUB_REMOTE_INVALID",
        message="GitHub 仓库地址无效",
        details={
            "supported_formats": [
                "https://github.com/owner/repository",
                "git@github.com:owner/repository.git",
                "ssh://git@github.com/owner/repository.git",
            ]
        },
    )


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
    repository = db.scalar(
        select(SourceRepository).where(
            SourceRepository.user_id == user_id,
            SourceRepository.project_id == project_id,
            SourceRepository.kind == repository_in.kind,
            SourceRepository.name == repository_in.name,
        )
    )
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


def resolve_github_repository(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    repository_in: GithubRepositoryResolve,
) -> SourceRepository:
    get_project(db, user_id=user_id, project_id=project_id)
    owner, name, remote_url = normalize_github_remote(repository_in.remote_url)
    db.execute(
        select(Project.id)
        .where(Project.id == project_id, Project.user_id == user_id)
        .with_for_update()
    )
    existing = db.scalar(
        select(SourceRepository).where(
            SourceRepository.user_id == user_id,
            SourceRepository.project_id == project_id,
            SourceRepository.provider == "github",
            SourceRepository.remote_owner == owner,
            SourceRepository.remote_name == name,
        )
    )

    if repository_in.local_repository_id is not None:
        repository = get_repository(
            db,
            user_id=user_id,
            project_id=project_id,
            repository_id=repository_in.local_repository_id,
        )
        if repository.kind != "local_folder":
            raise AppError(
                status_code=409,
                code="SOURCE_REPOSITORY_NOT_LOCAL",
                message="只能把 GitHub 地址关联到本地文件夹仓库",
                details={"repository_id": str(repository.id)},
            )
        if repository.provider is not None:
            if existing is not None and existing.id == repository.id:
                db.commit()
                db.refresh(repository)
                return repository
            raise AppError(
                status_code=409,
                code="SOURCE_REPOSITORY_REMOTE_CONFLICT",
                message="本地仓库已关联另一个远程仓库",
                details={"repository_id": str(repository.id)},
            )
        if existing is not None and existing.id != repository.id:
            raise AppError(
                status_code=409,
                code="GITHUB_REPOSITORY_ALREADY_REGISTERED",
                message="这个 GitHub 仓库已在当前项目中登记",
                details={"repository_id": str(existing.id)},
            )
    elif existing is not None:
        db.commit()
        db.refresh(existing)
        return existing
    else:
        repository = SourceRepository(
            user_id=user_id,
            project_id=project_id,
            name=f"{owner}/{name}",
            kind="git_remote",
        )

    repository.provider = "github"
    repository.remote_owner = owner
    repository.remote_name = name
    repository.remote_url = remote_url
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
    repository = db.scalar(
        select(SourceRepository).where(
            SourceRepository.id == repository_id,
            SourceRepository.user_id == user_id,
            SourceRepository.project_id == project_id,
        )
    )
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
