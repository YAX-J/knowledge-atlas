import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.core.errors import AppError
from app.models.domain import (
    ProcessingTask,
    RepositorySnapshot,
    RepositorySnapshotFile,
    SourceDocument,
    SourceRepository,
)
from app.schemas.repositories import (
    GithubRepositorySyncItem,
    GithubRepositorySyncResult,
)
from app.services import ingestion
from app.services.source_languages import CODE_SOURCE_TYPES
from app.services.repositories import get_repository, normalize_github_remote
from app.services.projects import get_project


MAX_GITHUB_IMPORT_FILES = 50
MAX_GITHUB_IMPORT_BYTES = 20 * 1024 * 1024


def _provider_error(response: httpx.Response) -> AppError:
    if response.status_code in {404, 422}:
        return AppError(
            status_code=404,
            code="GITHUB_REPOSITORY_UNAVAILABLE",
            message="GitHub 仓库或指定 ref 不存在，或者当前令牌无权读取",
        )
    if response.status_code in {403, 429}:
        return AppError(
            status_code=503,
            code="GITHUB_RATE_LIMITED",
            message="GitHub 暂时拒绝了同步请求，请检查令牌权限或稍后重试",
        )
    return AppError(
        status_code=502,
        code="GITHUB_PROVIDER_FAILED",
        message="GitHub 返回了无法处理的响应",
        details={"status_code": response.status_code},
    )


def _json_object(response: httpx.Response) -> dict[str, Any]:
    if not response.is_success:
        raise _provider_error(response)
    try:
        payload = response.json()
    except ValueError as exc:
        raise AppError(
            status_code=502,
            code="GITHUB_PROVIDER_FAILED",
            message="GitHub 返回了无效 JSON",
        ) from exc
    if not isinstance(payload, dict):
        raise AppError(
            status_code=502,
            code="GITHUB_PROVIDER_FAILED",
            message="GitHub 返回了无效数据结构",
        )
    return payload


def _get_json(client: httpx.Client, url: str, **kwargs: Any) -> dict[str, Any]:
    try:
        return _json_object(client.get(url, **kwargs))
    except httpx.HTTPError as exc:
        raise AppError(
            status_code=502,
            code="GITHUB_PROVIDER_FAILED",
            message="无法连接 GitHub，请稍后重试",
        ) from exc


def _supported_tree_entries(tree: object) -> list[dict[str, Any]]:
    if not isinstance(tree, list):
        raise AppError(
            status_code=502,
            code="GITHUB_PROVIDER_FAILED",
            message="GitHub tree 响应缺少文件列表",
        )
    entries: list[dict[str, Any]] = []
    for item in tree:
        if not isinstance(item, dict) or item.get("type") != "blob":
            continue
        path = item.get("path")
        sha = item.get("sha")
        size = item.get("size")
        if (
            isinstance(path, str)
            and isinstance(sha, str)
            and isinstance(size, int)
            and Path(path).suffix.lower() in ingestion.SOURCE_TYPE_BY_SUFFIX
        ):
            entries.append({"path": path, "sha": sha, "size": size})
    return sorted(entries, key=lambda item: item["path"])


def _get_blob(client: httpx.Client, url: str, *, max_bytes: int) -> bytes:
    try:
        with client.stream(
            "GET",
            url,
            headers={"Accept": "application/vnd.github.raw+json"},
        ) as response:
            if not response.is_success:
                raise _provider_error(response)
            content = bytearray()
            for chunk in response.iter_bytes():
                if len(content) + len(chunk) > max_bytes:
                    raise AppError(
                        status_code=413,
                        code="SOURCE_TOO_LARGE",
                        message="GitHub 文件超过单份资料大小限制",
                        details={"max_bytes": max_bytes},
                    )
                content.extend(chunk)
            return bytes(content)
    except httpx.HTTPError as exc:
        raise AppError(
            status_code=502,
            code="GITHUB_PROVIDER_FAILED",
            message="无法读取 GitHub 文件，请稍后重试",
        ) from exc


def _parse_github_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _update_provider_identity(
    db: Session,
    *,
    repository: SourceRepository,
    payload: dict[str, Any],
) -> None:
    provider_id_value = payload.get("id")
    provider_id = (
        str(provider_id_value)
        if isinstance(provider_id_value, (int, str)) and str(provider_id_value)
        else None
    )
    if (
        provider_id is not None
        and repository.provider_repository_id is not None
        and repository.provider_repository_id != provider_id
    ):
        raise AppError(
            status_code=409,
            code="GITHUB_REPOSITORY_IDENTITY_CHANGED",
            message="GitHub 仓库身份与已保存的 provider ID 不一致",
        )

    full_name = payload.get("full_name")
    normalized_identity: tuple[str, str, str] | None = None
    if isinstance(full_name, str) and "/" in full_name:
        try:
            normalized_identity = normalize_github_remote(
                f"https://github.com/{full_name}"
            )
        except AppError:
            normalized_identity = None

    owner = normalized_identity[0] if normalized_identity else repository.remote_owner
    name = normalized_identity[1] if normalized_identity else repository.remote_name
    conflict = db.scalar(
        select(SourceRepository).where(
            SourceRepository.user_id == repository.user_id,
            SourceRepository.project_id == repository.project_id,
            SourceRepository.id != repository.id,
            SourceRepository.provider == "github",
            or_(
                (
                    SourceRepository.remote_owner == owner
                ) & (
                    SourceRepository.remote_name == name
                ),
                SourceRepository.provider_repository_id == provider_id
                if provider_id is not None else False,
            ),
        )
    )
    if conflict is not None:
        raise AppError(
            status_code=409,
            code="GITHUB_REPOSITORY_IDENTITY_CONFLICT",
            message="GitHub 返回的新仓库身份已被当前项目中的其他仓库占用",
        )

    if provider_id is not None:
        repository.provider_repository_id = provider_id
    if normalized_identity is not None:
        repository.remote_owner, repository.remote_name, repository.remote_url = (
            normalized_identity
        )
        if repository.kind == "git_remote":
            repository.name = f"{normalized_identity[0]}/{normalized_identity[1]}"


def _snapshot(
    db: Session,
    *,
    repository_id: uuid.UUID,
    ref: str,
) -> RepositorySnapshot | None:
    query = (
        select(RepositorySnapshot)
        .where(
            RepositorySnapshot.repository_id == repository_id,
            RepositorySnapshot.ref == ref,
        )
        .options(selectinload(RepositorySnapshot.files))
    )
    query = query.order_by(
        RepositorySnapshot.created_at.desc(), RepositorySnapshot.id.desc()
    )
    return db.scalar(query.limit(1))


def _repeat_snapshot_result(
    snapshot: RepositorySnapshot,
) -> GithubRepositorySyncResult:
    items = [
        GithubRepositorySyncItem(
            path=item.path,
            source_id=item.source_id,
            task_id=item.task_id,
            status="unchanged" if item.source_id is not None else "skipped",
            error_code=item.error_code,
        )
        for item in sorted(snapshot.files, key=lambda item: item.path)
        if item.status != "deleted"
    ]
    return GithubRepositorySyncResult(
        repository_id=snapshot.repository_id,
        snapshot_id=snapshot.id,
        ref=snapshot.ref,
        commit_sha=snapshot.commit_sha,
        commit_url=snapshot.commit_url,
        imported_count=0,
        reused_count=0,
        unchanged_count=sum(item.status == "unchanged" for item in items),
        renamed_count=0,
        deleted_count=0,
        skipped_count=sum(item.status == "skipped" for item in items),
        truncated=snapshot.truncated,
        deletion_detection_complete=snapshot.deletion_detection_complete,
        items=items,
    )


def _reusable_snapshot_files(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    repository_id: uuid.UUID,
    blob_shas: set[str],
) -> list[tuple[RepositorySnapshotFile, str]]:
    """Validate source/task ownership and parser type before reusing provenance."""
    if not blob_shas:
        return []
    return list(db.execute(
        select(RepositorySnapshotFile, SourceDocument.source_type)
        .join(RepositorySnapshot, RepositorySnapshot.id == RepositorySnapshotFile.snapshot_id)
        .join(SourceDocument, SourceDocument.id == RepositorySnapshotFile.source_id)
        .join(ProcessingTask, ProcessingTask.id == RepositorySnapshotFile.task_id)
        .where(
            RepositorySnapshot.user_id == user_id,
            RepositorySnapshot.project_id == project_id,
            RepositorySnapshot.repository_id == repository_id,
            RepositorySnapshotFile.blob_sha.in_(blob_shas),
            SourceDocument.user_id == user_id,
            SourceDocument.project_id == project_id,
            SourceDocument.repository_id == repository_id,
            ProcessingTask.user_id == user_id,
            ProcessingTask.project_id == project_id,
            ProcessingTask.source_id == SourceDocument.id,
            or_(
                and_(SourceDocument.source_type.in_(tuple(CODE_SOURCE_TYPES)), ProcessingTask.type == "code_parsing"),
                and_(SourceDocument.source_type == "markdown",
                     ProcessingTask.type.in_(("markdown_parsing", "knowledge_extraction"))),
            ),
        )
        .order_by(
            RepositorySnapshot.created_at.desc(),
            RepositorySnapshot.id.desc(),
            RepositorySnapshotFile.created_at.desc(),
            RepositorySnapshotFile.id.desc(),
        )
    ).all())


def _snapshot_is_reusable(
    snapshot: RepositorySnapshot,
    reusable_types: dict[uuid.UUID, str],
) -> bool:
    if snapshot.truncated or not snapshot.deletion_detection_complete:
        return False
    for item in snapshot.files:
        if item.status == "deleted":
            continue
        if item.source_id is not None or item.task_id is not None:
            expected_type = ingestion.SOURCE_TYPE_BY_SUFFIX.get(Path(item.path).suffix.lower())
            if expected_type is None or reusable_types.get(item.id) != expected_type:
                return False
        elif item.error_code not in {"SOURCE_EMPTY", "SOURCE_ENCODING_INVALID", "SOURCE_PATH_INVALID"}:
            # Byte limits can change and truncated work can be retried. A
            # deterministic invalid blob/path need not be downloaded again.
            return False
    return True


def list_repository_snapshots(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    repository_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[RepositorySnapshot], int]:
    get_project(db, user_id=user_id, project_id=project_id)
    get_repository(
        db,
        user_id=user_id,
        project_id=project_id,
        repository_id=repository_id,
    )
    filters = (
        RepositorySnapshot.user_id == user_id,
        RepositorySnapshot.project_id == project_id,
        RepositorySnapshot.repository_id == repository_id,
    )
    total = db.scalar(
        select(func.count()).select_from(RepositorySnapshot).where(*filters)
    ) or 0
    items = list(db.scalars(
        select(RepositorySnapshot)
        .where(*filters)
        .order_by(RepositorySnapshot.created_at.desc(), RepositorySnapshot.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ))
    return items, total


def sync_github_repository(
    db: Session,
    *,
    settings: Settings,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    repository_id: uuid.UUID,
    requested_ref: str | None,
    rescan: bool = False,
) -> GithubRepositorySyncResult:
    repository = get_repository(
        db,
        user_id=user_id,
        project_id=project_id,
        repository_id=repository_id,
    )
    if (
        repository.provider != "github"
        or repository.remote_owner is None
        or repository.remote_name is None
    ):
        raise AppError(
            status_code=409,
            code="GITHUB_REPOSITORY_REQUIRED",
            message="只有已关联 GitHub remote 的仓库可以同步",
        )

    owner = quote(repository.remote_owner, safe="")
    name = quote(repository.remote_name, safe="")
    base_url = settings.github_api_base_url.rstrip("/")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": settings.github_api_version,
        "User-Agent": "Knowledge-Atlas/0.1",
    }
    if settings.github_token is not None:
        headers["Authorization"] = (
            f"Bearer {settings.github_token.get_secret_value()}"
        )

    with httpx.Client(
        headers=headers,
        timeout=httpx.Timeout(settings.github_timeout_seconds, connect=10),
    ) as client:
        repository_payload = _get_json(
            client, f"{base_url}/repos/{owner}/{name}"
        )
        _update_provider_identity(db, repository=repository, payload=repository_payload)
        # Continue against GitHub's canonical coordinates after a transfer or rename.
        owner = quote(repository.remote_owner or "", safe="")
        name = quote(repository.remote_name or "", safe="")
        selected_ref = requested_ref or repository_payload.get("default_branch")
        if not isinstance(selected_ref, str) or not selected_ref:
            raise AppError(
                status_code=502,
                code="GITHUB_PROVIDER_FAILED",
                message="GitHub 仓库响应缺少默认分支",
            )
        commit_payload = _get_json(
            client,
            f"{base_url}/repos/{owner}/{name}/commits/{quote(selected_ref, safe='')}",
        )
        commit_sha = commit_payload.get("sha")
        if not isinstance(commit_sha, str) or not commit_sha:
            raise AppError(
                status_code=502,
                code="GITHUB_PROVIDER_FAILED",
                message="GitHub commit 响应缺少 SHA",
            )

        previous_snapshot = _snapshot(
            db, repository_id=repository.id, ref=selected_ref
        )
        if (
            previous_snapshot is not None
            and previous_snapshot.commit_sha == commit_sha
            and not rescan
        ):
            reusable_types = {
                item.id: source_type
                for item, source_type in _reusable_snapshot_files(
                    db, user_id=user_id, project_id=project_id,
                    repository_id=repository.id,
                    blob_shas={item.blob_sha for item in previous_snapshot.files},
                )
            }
            if _snapshot_is_reusable(previous_snapshot, reusable_types):
                db.add(repository)
                db.commit()
                return _repeat_snapshot_result(previous_snapshot)

        commit_details = commit_payload.get("commit")
        tree_details = (
            commit_details.get("tree")
            if isinstance(commit_details, dict) else None
        )
        tree_sha = tree_details.get("sha") if isinstance(tree_details, dict) else None
        if not isinstance(tree_sha, str) or not tree_sha:
            raise AppError(
                status_code=502,
                code="GITHUB_PROVIDER_FAILED",
                message="GitHub commit 响应缺少 tree SHA",
            )
        tree_payload = _get_json(
            client,
            f"{base_url}/repos/{owner}/{name}/git/trees/{quote(tree_sha, safe='')}",
            params={"recursive": "1"},
        )
        entries = _supported_tree_entries(tree_payload.get("tree"))
        selected_entries = entries[:min(MAX_GITHUB_IMPORT_FILES, settings.github_import_max_files)]
        truncated = bool(tree_payload.get("truncated")) or len(entries) > len(
            selected_entries
        )
        deletion_detection_complete = not truncated

        previous_files = (
            [item for item in previous_snapshot.files if item.status != "deleted"]
            if previous_snapshot is not None else []
        )
        previous_by_path = {item.path: item for item in previous_files}
        previous_by_blob: defaultdict[
            tuple[str, str], list[RepositorySnapshotFile]
        ] = defaultdict(list)

        selected_blob_shas = {entry["sha"] for entry in selected_entries}
        known_files = _reusable_snapshot_files(
            db, user_id=user_id, project_id=project_id,
            repository_id=repository.id, blob_shas=selected_blob_shas,
        )
        reusable_types = {item.id: source_type for item, source_type in known_files}
        known_by_blob: dict[tuple[str, str], RepositorySnapshotFile] = {}
        for known_file, source_type in known_files:
            known_by_blob.setdefault((known_file.blob_sha, source_type), known_file)
        for item in previous_files:
            if item.id in reusable_types:
                previous_by_blob[(item.blob_sha, reusable_types[item.id])].append(item)

        current_paths = {entry["path"] for entry in selected_entries}
        current_paths_by_blob: defaultdict[str, list[str]] = defaultdict(list)
        for entry in selected_entries:
            current_paths_by_blob[entry["sha"]].append(entry["path"])
        renamed_from_paths: set[str] = set()
        downloaded_bytes = 0
        items: list[GithubRepositorySyncItem] = []
        file_records: list[tuple[str, str, int, GithubRepositorySyncItem]] = []
        source_path_updates: list[tuple[uuid.UUID, str]] = []

        for entry in selected_entries:
            path = entry["path"]
            blob_sha = entry["sha"]
            size = entry["size"]
            source_type = ingestion.SOURCE_TYPE_BY_SUFFIX[Path(path).suffix.lower()]
            previous_at_path = previous_by_path.get(path)
            if (
                previous_at_path is not None
                and previous_at_path.blob_sha == blob_sha
                and reusable_types.get(previous_at_path.id) == source_type
            ):
                item = GithubRepositorySyncItem(
                    path=path,
                    source_id=previous_at_path.source_id,
                    task_id=previous_at_path.task_id,
                    status="unchanged",
                )
                items.append(item)
                file_records.append((path, blob_sha, size, item))
                continue

            if size <= 0:
                item = GithubRepositorySyncItem(
                    path=path, status="skipped", error_code="SOURCE_EMPTY"
                )
                items.append(item)
                file_records.append((path, blob_sha, size, item))
                continue
            if size > settings.max_upload_bytes:
                item = GithubRepositorySyncItem(
                    path=path, status="skipped", error_code="SOURCE_TOO_LARGE"
                )
                items.append(item)
                file_records.append((path, blob_sha, size, item))
                continue

            blob_candidates = previous_by_blob.get((blob_sha, source_type), [])
            rename_candidates = [
                candidate
                for candidate in blob_candidates
                if candidate.path not in current_paths
                and candidate.path not in renamed_from_paths
            ]
            if (
                previous_at_path is None
                and deletion_detection_complete
                and len(rename_candidates) == 1
                and len(current_paths_by_blob[blob_sha]) == 1
            ):
                candidate = rename_candidates[0]
                renamed_from_paths.add(candidate.path)
                item = GithubRepositorySyncItem(
                    path=path,
                    previous_path=candidate.path,
                    source_id=candidate.source_id,
                    task_id=candidate.task_id,
                    status="renamed",
                )
                items.append(item)
                file_records.append((path, blob_sha, size, item))
                if candidate.source_id is not None and not any(
                    other.source_id == candidate.source_id
                    and other.path in current_paths
                    and other.path != candidate.path
                    for other in previous_files
                ):
                    source_path_updates.append((candidate.source_id, path))
                continue

            known_file = known_by_blob.get((blob_sha, source_type))
            if known_file is not None:
                item = GithubRepositorySyncItem(
                    path=path,
                    source_id=known_file.source_id,
                    task_id=known_file.task_id,
                    status="reused",
                )
                items.append(item)
                file_records.append((path, blob_sha, size, item))
                continue

            if downloaded_bytes + size > MAX_GITHUB_IMPORT_BYTES:
                truncated = True
                deletion_detection_complete = False
                item = GithubRepositorySyncItem(
                    path=path,
                    status="skipped",
                    error_code="GITHUB_IMPORT_TOTAL_SIZE_EXCEEDED",
                )
                items.append(item)
                file_records.append((path, blob_sha, size, item))
                continue
            try:
                raw_content = _get_blob(
                    client,
                    f"{base_url}/repos/{owner}/{name}/git/blobs/"
                    f"{quote(blob_sha, safe='')}",
                    max_bytes=settings.max_upload_bytes,
                )
            except AppError as exc:
                if exc.code == "SOURCE_TOO_LARGE":
                    item = GithubRepositorySyncItem(
                        path=path, status="skipped", error_code=exc.code
                    )
                    items.append(item)
                    file_records.append((path, blob_sha, size, item))
                    continue
                raise
            if downloaded_bytes + len(raw_content) > MAX_GITHUB_IMPORT_BYTES:
                truncated = True
                deletion_detection_complete = False
                item = GithubRepositorySyncItem(
                    path=path,
                    status="skipped",
                    error_code="GITHUB_IMPORT_TOTAL_SIZE_EXCEEDED",
                )
                items.append(item)
                file_records.append((path, blob_sha, size, item))
                continue
            downloaded_bytes += len(raw_content)
            try:
                source, task, reused = ingestion.create_source_and_task_from_bytes(
                    db,
                    settings=settings,
                    user_id=user_id,
                    project_id=project_id,
                    filename=Path(path).name,
                    raw_content=raw_content,
                    source_type=None,
                    relative_path=path,
                    repository_id=repository.id,
                )
            except AppError as exc:
                if exc.code in {
                    "SOURCE_EMPTY",
                    "SOURCE_ENCODING_INVALID",
                    "SOURCE_PATH_INVALID",
                    "SOURCE_TOO_LARGE",
                }:
                    item = GithubRepositorySyncItem(
                        path=path, status="skipped", error_code=exc.code
                    )
                    items.append(item)
                    file_records.append((path, blob_sha, size, item))
                    continue
                raise
            item = GithubRepositorySyncItem(
                path=path,
                source_id=source.id,
                task_id=task.id,
                status="reused" if reused else "imported",
            )
            items.append(item)
            file_records.append((path, blob_sha, size, item))

        if deletion_detection_complete:
            for previous in sorted(previous_files, key=lambda item: item.path):
                if (
                    previous.path not in current_paths
                    and previous.path not in renamed_from_paths
                ):
                    item = GithubRepositorySyncItem(
                        path=previous.path,
                        source_id=previous.source_id,
                        task_id=previous.task_id,
                        status="deleted",
                    )
                    items.append(item)
                    file_records.append(
                        (previous.path, previous.blob_sha, previous.size_bytes, item)
                    )

        commit_info = commit_details if isinstance(commit_details, dict) else {}
        commit_author = commit_info.get("committer") or commit_info.get("author")
        commit_url = commit_payload.get("html_url")
        if not isinstance(commit_url, str) or not commit_url:
            commit_url = f"{repository.remote_url}/commit/{commit_sha}"
        snapshot = RepositorySnapshot(
            user_id=user_id,
            project_id=project_id,
            repository_id=repository.id,
            provider="github",
            ref=selected_ref,
            commit_sha=commit_sha,
            tree_sha=tree_sha,
            commit_url=commit_url,
            commit_message=(
                commit_info.get("message")
                if isinstance(commit_info.get("message"), str) else ""
            ),
            committed_at=_parse_github_datetime(
                commit_author.get("date") if isinstance(commit_author, dict) else None
            ),
            truncated=truncated,
            deletion_detection_complete=deletion_detection_complete,
            file_count=len(selected_entries),
            imported_count=sum(item.status == "imported" for item in items),
            reused_count=sum(item.status == "reused" for item in items),
            unchanged_count=sum(item.status == "unchanged" for item in items),
            renamed_count=sum(item.status == "renamed" for item in items),
            deleted_count=sum(item.status == "deleted" for item in items),
            skipped_count=sum(item.status == "skipped" for item in items),
            downloaded_bytes=downloaded_bytes,
        )
        db.add(snapshot)
        db.flush()
        for path, blob_sha, size, item in file_records:
            db.add(RepositorySnapshotFile(
                snapshot_id=snapshot.id,
                source_id=item.source_id,
                task_id=item.task_id,
                path=path,
                previous_path=item.previous_path,
                blob_sha=blob_sha,
                size_bytes=size,
                status=item.status,
                error_code=item.error_code,
            ))
        for source_id, path in source_path_updates:
            source = ingestion.get_source(db, user_id=user_id, source_id=source_id)
            source.relative_path = path
            source.original_name = Path(path).name
        db.add(repository)
        db.commit()

    return GithubRepositorySyncResult(
        repository_id=repository.id,
        snapshot_id=snapshot.id,
        ref=selected_ref,
        commit_sha=commit_sha,
        commit_url=commit_url,
        imported_count=snapshot.imported_count,
        reused_count=snapshot.reused_count,
        unchanged_count=snapshot.unchanged_count,
        renamed_count=snapshot.renamed_count,
        deleted_count=snapshot.deleted_count,
        skipped_count=snapshot.skipped_count,
        truncated=truncated,
        deletion_detection_complete=deletion_detection_complete,
        items=items,
    )
