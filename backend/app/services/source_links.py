import uuid
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    RepositorySnapshot,
    RepositorySnapshotFile,
    SourceDocument,
    SourceRepository,
)


def github_file_urls(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    source_ids: list[uuid.UUID],
) -> dict[uuid.UUID, str]:
    """Return each source's latest immutable GitHub file URL, when available."""
    if not source_ids:
        return {}

    rows = db.execute(
        select(
            RepositorySnapshotFile.source_id,
            RepositorySnapshotFile.path,
            RepositorySnapshot.commit_sha,
            SourceRepository.remote_url,
        )
        .join(
            RepositorySnapshot,
            RepositorySnapshot.id == RepositorySnapshotFile.snapshot_id,
        )
        .join(
            SourceRepository,
            SourceRepository.id == RepositorySnapshot.repository_id,
        )
        .join(
            SourceDocument,
            SourceDocument.id == RepositorySnapshotFile.source_id,
        )
        .where(
            RepositorySnapshotFile.source_id.in_(source_ids),
            RepositorySnapshotFile.status != "deleted",
            RepositorySnapshot.user_id == user_id,
            RepositorySnapshot.project_id == project_id,
            SourceRepository.user_id == user_id,
            SourceRepository.project_id == project_id,
            SourceRepository.provider == "github",
            SourceRepository.remote_url.is_not(None),
            SourceDocument.user_id == user_id,
            SourceDocument.project_id == project_id,
        )
        .order_by(
            RepositorySnapshot.created_at.desc(),
            RepositorySnapshot.id.desc(),
            (RepositorySnapshotFile.path == SourceDocument.relative_path).desc(),
            RepositorySnapshotFile.path,
        )
    )
    urls: dict[uuid.UUID, str] = {}
    for source_id, path, commit_sha, remote_url in rows:
        if source_id is None or source_id in urls or remote_url is None:
            continue
        urls[source_id] = (
            f"{remote_url.rstrip('/')}/blob/{quote(commit_sha, safe='')}/"
            f"{quote(path, safe='/')}"
        )
    return urls


def github_line_url(
    file_url: str | None,
    *,
    start_line: int,
    end_line: int,
) -> str | None:
    if file_url is None:
        return None
    fragment = f"L{start_line}"
    if end_line != start_line:
        fragment += f"-L{end_line}"
    return f"{file_url}#{fragment}"
