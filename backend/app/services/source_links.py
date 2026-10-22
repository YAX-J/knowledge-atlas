import uuid
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    GithubPullReviewVersion,
    GithubWorkItemVersion,
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
    """Return each source's GitHub file or canonical work-item URL."""
    if not source_ids:
        return {}

    commit_rows = db.execute(select(
        RepositorySnapshot.commit_source_id, RepositorySnapshot.commit_sha, SourceRepository.remote_url,
    ).join(SourceRepository, SourceRepository.id == RepositorySnapshot.repository_id)
     .join(SourceDocument, SourceDocument.id == RepositorySnapshot.commit_source_id).where(
        RepositorySnapshot.commit_source_id.in_(source_ids),
        RepositorySnapshot.user_id == user_id, RepositorySnapshot.project_id == project_id,
        SourceRepository.user_id == user_id, SourceRepository.project_id == project_id,
        SourceRepository.provider == "github", SourceRepository.remote_url.is_not(None),
        SourceDocument.user_id == user_id, SourceDocument.project_id == project_id,
        SourceDocument.repository_id == SourceRepository.id,
    ).order_by(RepositorySnapshot.created_at.desc(), RepositorySnapshot.id.desc()))
    urls: dict[uuid.UUID, str] = {}
    for source_id, sha, remote_url in commit_rows:
        if source_id is not None and remote_url is not None:
            urls.setdefault(source_id, f"{remote_url}/commit/{quote(sha.lower(), safe='')}")

    work_item_rows = db.execute(
        select(
            GithubWorkItemVersion.source_id,
            GithubWorkItemVersion.html_url,
        )
        .where(
            GithubWorkItemVersion.source_id.in_(source_ids),
            GithubWorkItemVersion.user_id == user_id,
            GithubWorkItemVersion.project_id == project_id,
            GithubWorkItemVersion.source_id.is_not(None),
        )
        .order_by(
            GithubWorkItemVersion.provider_updated_at.desc(),
            GithubWorkItemVersion.created_at.desc(),
        )
    )
    for source_id, html_url in work_item_rows:
        if source_id is not None and source_id not in urls:
            urls[source_id] = html_url

    review_rows = db.execute(
        select(
            GithubPullReviewVersion.source_id,
            GithubPullReviewVersion.html_url,
        )
        .where(
            GithubPullReviewVersion.source_id.in_(source_ids),
            GithubPullReviewVersion.user_id == user_id,
            GithubPullReviewVersion.project_id == project_id,
            GithubPullReviewVersion.source_id.is_not(None),
        )
        .order_by(GithubPullReviewVersion.created_at.desc())
    )
    for source_id, html_url in review_rows:
        if source_id is not None and source_id not in urls:
            urls[source_id] = html_url

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
    if "/blob/" not in file_url and (
        "/issues/" in file_url or "/pull/" in file_url or "/commit/" in file_url
    ):
        return file_url
    fragment = f"L{start_line}"
    if end_line != start_line:
        fragment += f"-L{end_line}"
    return f"{file_url}#{fragment}"
