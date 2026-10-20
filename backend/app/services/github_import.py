import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.repositories import (
    GithubRepositorySyncItem,
    GithubRepositorySyncResult,
)
from app.services import ingestion
from app.services.repositories import get_repository


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


def sync_github_repository(
    db: Session,
    *,
    settings: Settings,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    repository_id: uuid.UUID,
    requested_ref: str | None,
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
        selected_entries = entries[:MAX_GITHUB_IMPORT_FILES]
        truncated = bool(tree_payload.get("truncated")) or len(entries) > len(
            selected_entries
        )
        downloaded_bytes = 0
        items: list[GithubRepositorySyncItem] = []
        for entry in selected_entries:
            path = entry["path"]
            size = entry["size"]
            if size <= 0:
                items.append(GithubRepositorySyncItem(
                    path=path, status="skipped", error_code="SOURCE_EMPTY"
                ))
                continue
            if size > settings.max_upload_bytes:
                items.append(GithubRepositorySyncItem(
                    path=path, status="skipped", error_code="SOURCE_TOO_LARGE"
                ))
                continue
            if downloaded_bytes + size > MAX_GITHUB_IMPORT_BYTES:
                truncated = True
                items.append(GithubRepositorySyncItem(
                    path=path,
                    status="skipped",
                    error_code="GITHUB_IMPORT_TOTAL_SIZE_EXCEEDED",
                ))
                continue
            try:
                raw_content = _get_blob(
                    client,
                    f"{base_url}/repos/{owner}/{name}/git/blobs/"
                    f"{quote(entry['sha'], safe='')}",
                    max_bytes=settings.max_upload_bytes,
                )
            except AppError as exc:
                if exc.code == "SOURCE_TOO_LARGE":
                    items.append(GithubRepositorySyncItem(
                        path=path, status="skipped", error_code=exc.code
                    ))
                    continue
                raise
            try:
                if downloaded_bytes + len(raw_content) > MAX_GITHUB_IMPORT_BYTES:
                    truncated = True
                    items.append(GithubRepositorySyncItem(
                        path=path,
                        status="skipped",
                        error_code="GITHUB_IMPORT_TOTAL_SIZE_EXCEEDED",
                    ))
                    continue
                downloaded_bytes += len(raw_content)
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
                    db.rollback()
                    items.append(GithubRepositorySyncItem(
                        path=path, status="skipped", error_code=exc.code
                    ))
                    continue
                raise
            items.append(GithubRepositorySyncItem(
                path=path,
                source_id=source.id,
                task_id=task.id,
                status="reused" if reused else "imported",
            ))

    return GithubRepositorySyncResult(
        repository_id=repository.id,
        ref=selected_ref,
        commit_sha=commit_sha,
        imported_count=sum(item.status == "imported" for item in items),
        reused_count=sum(item.status == "reused" for item in items),
        skipped_count=sum(item.status == "skipped" for item in items),
        truncated=truncated,
        items=items,
    )
