"""Read persisted file provenance without contacting the Git provider."""

import re
import uuid
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.domain import ProcessingTask, RepositorySnapshot, RepositorySnapshotFile, SourceDocument
from app.schemas.repositories import RepositorySnapshotFileList, RepositorySnapshotFileRead
from app.services import ingestion
from app.services.projects import get_project
from app.services.repositories import get_repository


def list_snapshot_files(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID,
    repository_id: uuid.UUID, snapshot_id: uuid.UUID, page: int, page_size: int,
) -> RepositorySnapshotFileList:
    get_project(db, user_id=user_id, project_id=project_id)
    repository = get_repository(db, user_id=user_id, project_id=project_id, repository_id=repository_id)
    snapshot = db.scalar(select(RepositorySnapshot).where(
        RepositorySnapshot.id == snapshot_id, RepositorySnapshot.user_id == user_id,
        RepositorySnapshot.project_id == project_id, RepositorySnapshot.repository_id == repository_id,
    ))
    if snapshot is None:
        raise AppError(status_code=404, code="REPOSITORY_SNAPSHOT_NOT_FOUND", message="仓库同步快照不存在")
    scope = RepositorySnapshotFile.snapshot_id == snapshot.id
    total = db.scalar(select(func.count()).select_from(RepositorySnapshotFile).where(scope)) or 0
    # Project only link metadata: do not load source bodies or task results.
    rows = db.execute(select(
        RepositorySnapshotFile, SourceDocument.id, SourceDocument.source_type,
        SourceDocument.status, ProcessingTask.id,
    ).outerjoin(SourceDocument, and_(
        SourceDocument.id == RepositorySnapshotFile.source_id,
        SourceDocument.user_id == user_id, SourceDocument.project_id == project_id,
        SourceDocument.repository_id == repository_id,
    )).outerjoin(ProcessingTask, and_(
        ProcessingTask.id == RepositorySnapshotFile.task_id,
        ProcessingTask.source_id == SourceDocument.id,
        ProcessingTask.user_id == user_id, ProcessingTask.project_id == project_id,
        or_(
            and_(SourceDocument.source_type == "java", ProcessingTask.type == "code_parsing"),
            and_(SourceDocument.source_type == "markdown", ProcessingTask.type.in_(("markdown_parsing", "knowledge_extraction"))),
        ),
    )).where(scope).order_by(RepositorySnapshotFile.path, RepositorySnapshotFile.id)
      .offset((page - 1) * page_size).limit(page_size))
    items = []
    for item, source_id, source_type, source_status, task_id in rows:
        expected_type = ingestion.SOURCE_TYPE_BY_SUFFIX.get(Path(item.path).suffix.lower())
        if item.status == "skipped" or source_type != expected_type or expected_type is None:
            source_id, source_status, task_id = None, None, None
        git_url = None
        # Deleted paths do not exist in this commit; never invent a file link.
        if item.status != "deleted" and repository.provider == "github" and repository.remote_url and re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", snapshot.commit_sha):
            try:
                path = ingestion.normalize_relative_path(item.path, original_name=Path(item.path).name)
            except AppError:
                path = None
            if path:
                git_url = f"{repository.remote_url}/blob/{quote(snapshot.commit_sha.lower(), safe='')}/{quote(path, safe='/')}"
        items.append(RepositorySnapshotFileRead(
            id=item.id, path=item.path, previous_path=item.previous_path,
            blob_sha=item.blob_sha, size_bytes=item.size_bytes, status=item.status,
            error_code=item.error_code, source_id=source_id, task_id=task_id,
            source_status=source_status.value if source_status is not None else None, git_url=git_url,
        ))
    return RepositorySnapshotFileList(
        snapshot_id=snapshot.id, repository_id=repository.id, commit_sha=snapshot.commit_sha,
        truncated=snapshot.truncated, deletion_detection_complete=snapshot.deletion_detection_complete,
        items=items, page=page, page_size=page_size, total=total,
    )
