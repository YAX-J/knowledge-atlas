"""Import saved commit metadata through the ordinary evidence source pipeline."""

import re
import uuid
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.domain import ProcessingTask, RepositorySnapshot, SourceDocument
from app.schemas.repositories import SnapshotCommitSourceRead
from app.services import ingestion
from app.services.repositories import get_repository
from app.services.projects import get_project


def import_snapshot_commit(
    db: Session, *, settings: Settings, user_id: uuid.UUID,
    project_id: uuid.UUID, repository_id: uuid.UUID, snapshot_id: uuid.UUID,
) -> SnapshotCommitSourceRead:
    get_project(db, user_id=user_id, project_id=project_id)
    repository = get_repository(db, user_id=user_id, project_id=project_id, repository_id=repository_id)
    snapshot = db.scalar(select(RepositorySnapshot).where(
        RepositorySnapshot.id == snapshot_id,
        RepositorySnapshot.user_id == user_id,
        RepositorySnapshot.project_id == project_id,
        RepositorySnapshot.repository_id == repository_id,
        RepositorySnapshot.provider == "github",
    ))
    if snapshot is None:
        raise AppError(status_code=404, code="REPOSITORY_SNAPSHOT_NOT_FOUND", message="仓库同步快照不存在")
    if repository.provider != "github" or not repository.remote_url:
        raise AppError(status_code=409, code="GITHUB_REPOSITORY_REQUIRED", message="需要已关联的 GitHub 仓库")
    sha = snapshot.commit_sha.lower()
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", sha):
        raise AppError(status_code=409, code="SNAPSHOT_COMMIT_INVALID", message="快照中的 Commit SHA 无效，请重新同步")
    linked = db.execute(select(SourceDocument, ProcessingTask).join(
        ProcessingTask, ProcessingTask.source_id == SourceDocument.id,
    ).where(
        SourceDocument.id == snapshot.commit_source_id,
        SourceDocument.user_id == user_id, SourceDocument.project_id == project_id,
        SourceDocument.repository_id == repository_id, SourceDocument.source_type == "markdown",
        ProcessingTask.id == snapshot.commit_task_id,
        ProcessingTask.user_id == user_id, ProcessingTask.project_id == project_id,
        ProcessingTask.type == "markdown_parsing",
    )).first()
    reused = linked is not None
    if linked is not None:
        source, task = linked
    else:
        timestamp = snapshot.committed_at
        if timestamp is not None:
            timestamp = (timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp).astimezone(UTC)
        # Ref, sync counters, display coordinates and remote URL are deliberately
        # excluded: the same immutable commit imported via another ref or after
        # a repository rename must render the same bytes.
        message = snapshot.commit_message or ""
        markdown = (
            f"# GitHub Commit {sha}\n\n"
            f"- Commit SHA: `{sha}`\n"
            f"- Committed at (UTC): {timestamp.isoformat() if timestamp else 'Not available'}\n\n"
            "## Commit message\n\n"
            + ("\n".join(f"> {line}" for line in message.splitlines()) if message else "> (No commit message saved)")
            + "\n\n## Source boundary\n\n"
            "This source contains saved commit metadata and the commit message only. "
            "It does not include a patch, changed-file list, parent history, or evidence that the stated change works.\n"
        )
        source, task, reused = ingestion.create_source_and_task_from_bytes(
            db, settings=settings, user_id=user_id, project_id=project_id,
            filename=f"commit-{sha}.md", raw_content=markdown.encode("utf-8"),
            source_type="markdown", relative_path=f"github/commits/commit-{sha}.md", repository_id=repository_id,
        )
        snapshot.commit_source_id = source.id
        snapshot.commit_task_id = task.id
        db.commit()
    return SnapshotCommitSourceRead(
        snapshot_id=snapshot.id, source_id=source.id, task_id=task.id,
        status=task.status.value, reused=reused,
        git_url=f"{repository.remote_url}/commit/{sha}",
    )
