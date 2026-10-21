import hashlib
import uuid
from datetime import datetime
from typing import Any, Literal
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.domain import GithubPullReviewVersion, GithubWorkItemVersion
from app.schemas.repositories import (
    GithubWorkItemImportItem,
    GithubWorkItemImportResult,
)
from app.services import github_import, ingestion
from app.services.repositories import get_repository


MAX_GITHUB_WORK_ITEMS = 20
MAX_GITHUB_COMMENTS_PER_ITEM = 20
MAX_GITHUB_REVIEWS_PER_PULL = 20
MAX_GITHUB_REVIEW_COMMENTS_PER_PULL = 20


def _json_array(response: httpx.Response) -> list[dict[str, Any]]:
    if not response.is_success:
        raise github_import._provider_error(response)
    try:
        payload = response.json()
    except ValueError as exc:
        raise AppError(
            status_code=502,
            code="GITHUB_PROVIDER_FAILED",
            message="GitHub 返回了无效 JSON",
        ) from exc
    if not isinstance(payload, list) or not all(
        isinstance(item, dict) for item in payload
    ):
        raise AppError(
            status_code=502,
            code="GITHUB_PROVIDER_FAILED",
            message="GitHub 返回了无效数据结构",
        )
    return payload


def _get_json_array(
    client: httpx.Client, url: str, **kwargs: Any
) -> list[dict[str, Any]]:
    try:
        return _json_array(client.get(url, **kwargs))
    except httpx.HTTPError as exc:
        raise AppError(
            status_code=502,
            code="GITHUB_PROVIDER_FAILED",
            message="无法连接 GitHub，请稍后重试",
        ) from exc


def _get_bounded_json_array(
    client: httpx.Client,
    url: str,
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], bool]:
    try:
        response = client.get(url, params={"per_page": limit})
        payload = _json_array(response)
    except httpx.HTTPError as exc:
        raise AppError(
            status_code=502,
            code="GITHUB_PROVIDER_FAILED",
            message="无法连接 GitHub，请稍后重试",
        ) from exc
    return payload[:limit], "next" in response.links


def _required_item_fields(
    payload: dict[str, Any], *, forced_type: str | None = None
) -> tuple[str, int, str, str, str, datetime, str]:
    provider_id = payload.get("id")
    number = payload.get("number")
    title = payload.get("title")
    html_url = payload.get("html_url")
    state = payload.get("state")
    provider_updated_at = github_import._parse_github_datetime(
        payload.get("updated_at")
    )
    item_type = forced_type or (
        "pull_request" if isinstance(payload.get("pull_request"), dict) else "issue"
    )
    if not (
        isinstance(provider_id, (int, str))
        and str(provider_id)
        and isinstance(number, int)
        and number >= 1
        and isinstance(title, str)
        and isinstance(html_url, str)
        and html_url.startswith("https://github.com/")
        and state in {"open", "closed"}
        and provider_updated_at is not None
    ):
        raise AppError(
            status_code=502,
            code="GITHUB_PROVIDER_FAILED",
            message="GitHub Issue/PR 响应缺少必要字段",
        )
    return (
        str(provider_id), number, item_type, title.strip(), html_url,
        provider_updated_at, state,
    )


def _actor_login(value: object) -> str:
    if isinstance(value, dict) and isinstance(value.get("login"), str):
        return value["login"]
    return "unknown"


def _single_line(value: str) -> str:
    return " ".join(value.splitlines()).strip()


def _render_markdown(
    payload: dict[str, Any],
    *,
    item_type: str,
    number: int,
    title: str,
    html_url: str,
    comments: list[dict[str, Any]],
    comments_truncated: bool,
) -> str:
    kind_label = "Pull Request" if item_type == "pull_request" else "Issue"
    labels = [
        item["name"]
        for item in payload.get("labels", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ] if isinstance(payload.get("labels"), list) else []
    lines = [
        f"# {kind_label} #{number}: {_single_line(title)}",
        "",
        f"- Type: {item_type}",
        f"- State: {payload.get('state')}",
        f"- Author: @{_actor_login(payload.get('user'))}",
        f"- Created: {payload.get('created_at', '')}",
        f"- Updated: {payload.get('updated_at', '')}",
        f"- URL: {html_url}",
    ]
    if labels:
        lines.append(f"- Labels: {', '.join(labels)}")
    if item_type == "pull_request":
        head = payload.get("head")
        base = payload.get("base")
        if isinstance(head, dict) and isinstance(head.get("label"), str):
            lines.append(f"- Head: {head['label']}")
        if isinstance(base, dict) and isinstance(base.get("label"), str):
            lines.append(f"- Base: {base['label']}")
        merged = payload.get("merged")
        if isinstance(merged, bool):
            lines.append(f"- Merged: {'yes' if merged else 'no'}")
    body = payload.get("body")
    description = (
        body.strip()
        if isinstance(body, str) and body.strip()
        else "_No description provided._"
    )
    lines.extend(["", "## Description", "", description])
    lines.extend(["", "## Comments", ""])
    if not comments:
        lines.append("_No comments imported._")
    for comment in comments:
        comment_body = comment.get("body")
        if not isinstance(comment_body, str) or not comment_body.strip():
            continue
        lines.extend([
            f"### @{_actor_login(comment.get('user'))} · {comment.get('created_at', '')}",
            "",
            comment_body.strip(),
            "",
        ])
    if comments_truncated:
        lines.extend([
            "",
            f"_Comments truncated after {MAX_GITHUB_COMMENTS_PER_ITEM} entries._",
        ])
    return "\n".join(lines).rstrip() + "\n"


def _stable_activity_key(payload: dict[str, Any]) -> tuple[str, str]:
    timestamp = payload.get("submitted_at") or payload.get("created_at") or ""
    provider_id = payload.get("id")
    return str(timestamp), str(provider_id) if provider_id is not None else ""


def _render_pull_review_markdown(
    *,
    number: int,
    html_url: str,
    reviews: list[dict[str, Any]],
    review_comments: list[dict[str, Any]],
    reviews_truncated: bool,
    review_comments_truncated: bool,
) -> str:
    lines = [
        f"# Pull Request #{number} review activity",
        "",
        "- Type: pull_request_reviews",
        f"- URL: {html_url}",
        "",
        "## Reviews",
        "",
    ]
    if not reviews:
        lines.append("_No reviews imported._")
    for review in sorted(reviews, key=_stable_activity_key):
        state = _single_line(str(review.get("state") or "unknown")).upper()
        submitted_at = review.get("submitted_at") or ""
        lines.extend([
            f"### {state} by @{_actor_login(review.get('user'))} · {submitted_at}",
            "",
        ])
        html_url_value = review.get("html_url")
        if isinstance(html_url_value, str) and html_url_value.startswith("https://"):
            lines.append(f"- URL: {html_url_value}")
        commit_id = review.get("commit_id")
        if isinstance(commit_id, str) and commit_id:
            lines.append(f"- Commit: `{_single_line(commit_id)}`")
        body = review.get("body")
        lines.extend([
            "",
            body.strip() if isinstance(body, str) and body.strip() else "_No review body._",
            "",
        ])
    if reviews_truncated:
        lines.extend([
            f"_Reviews truncated after {MAX_GITHUB_REVIEWS_PER_PULL} entries._",
            "",
        ])

    lines.extend(["## Review comments", ""])
    if not review_comments:
        lines.append("_No review comments imported._")
    for comment in sorted(review_comments, key=_stable_activity_key):
        path = comment.get("path")
        path_label = _single_line(path) if isinstance(path, str) else "unknown path"
        line = comment.get("line")
        if not isinstance(line, int):
            line = comment.get("original_line")
        location = f"{path_label}:{line}" if isinstance(line, int) else path_label
        lines.extend([
            f"### @{_actor_login(comment.get('user'))} · `{location}` · "
            f"{comment.get('created_at', '')}",
            "",
        ])
        html_url_value = comment.get("html_url")
        if isinstance(html_url_value, str) and html_url_value.startswith("https://"):
            lines.append(f"- URL: {html_url_value}")
        reply_to = comment.get("in_reply_to_id")
        if isinstance(reply_to, (int, str)):
            lines.append(f"- Reply to review comment: {reply_to}")
        body = comment.get("body")
        lines.extend([
            "",
            body.strip() if isinstance(body, str) and body.strip() else "_No comment body._",
            "",
        ])
    if review_comments_truncated:
        lines.append(
            "_Review comments truncated after "
            f"{MAX_GITHUB_REVIEW_COMMENTS_PER_PULL} entries._"
        )
    return "\n".join(lines).rstrip() + "\n"


def _existing_pull_review_version(
    db: Session,
    *,
    repository_id: uuid.UUID,
    provider_pull_id: str,
    activity_digest: str,
) -> GithubPullReviewVersion | None:
    return db.scalar(
        select(GithubPullReviewVersion).where(
            GithubPullReviewVersion.repository_id == repository_id,
            GithubPullReviewVersion.provider_pull_id == provider_pull_id,
            GithubPullReviewVersion.activity_digest == activity_digest,
        )
    )


def _import_pull_review_activity(
    db: Session,
    *,
    client: httpx.Client,
    settings: Settings,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    repository_id: uuid.UUID,
    base_url: str,
    owner: str,
    name: str,
    provider_pull_id: str,
    number: int,
    html_url: str,
    item: GithubWorkItemImportItem,
) -> None:
    reviews, reviews_truncated = _get_bounded_json_array(
        client,
        f"{base_url}/repos/{owner}/{name}/pulls/{number}/reviews",
        limit=MAX_GITHUB_REVIEWS_PER_PULL,
    )
    review_comments, review_comments_truncated = _get_bounded_json_array(
        client,
        f"{base_url}/repos/{owner}/{name}/pulls/{number}/comments",
        limit=MAX_GITHUB_REVIEW_COMMENTS_PER_PULL,
    )
    markdown = _render_pull_review_markdown(
        number=number,
        html_url=html_url,
        reviews=reviews,
        review_comments=review_comments,
        reviews_truncated=reviews_truncated,
        review_comments_truncated=review_comments_truncated,
    )
    activity_digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    item.reviews_count = len(reviews)
    item.review_comments_count = len(review_comments)
    item.reviews_truncated = reviews_truncated
    item.review_comments_truncated = review_comments_truncated

    existing = _existing_pull_review_version(
        db,
        repository_id=repository_id,
        provider_pull_id=provider_pull_id,
        activity_digest=activity_digest,
    )
    if existing is not None:
        item.review_source_id = existing.source_id
        item.review_task_id = existing.task_id
        item.review_status = "reused"
        return

    filename = f"pull-request-{number}-reviews.md"
    try:
        source, task, _ = ingestion.create_source_and_task_from_bytes(
            db,
            settings=settings,
            user_id=user_id,
            project_id=project_id,
            filename=filename,
            raw_content=markdown.encode("utf-8"),
            source_type="markdown",
            relative_path=f"github/pull-request-reviews/{filename}",
            repository_id=repository_id,
        )
    except AppError as exc:
        item.review_status = "skipped"
        item.review_error_code = exc.code
        return

    version = GithubPullReviewVersion(
        user_id=user_id,
        project_id=project_id,
        repository_id=repository_id,
        source_id=source.id,
        task_id=task.id,
        provider_pull_id=provider_pull_id,
        number=number,
        html_url=html_url,
        activity_digest=activity_digest,
        reviews_count=len(reviews),
        review_comments_count=len(review_comments),
        reviews_truncated=reviews_truncated,
        review_comments_truncated=review_comments_truncated,
    )
    db.add(version)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = _existing_pull_review_version(
            db,
            repository_id=repository_id,
            provider_pull_id=provider_pull_id,
            activity_digest=activity_digest,
        )
        if winner is None:
            raise
        item.review_source_id = winner.source_id
        item.review_task_id = winner.task_id
        item.review_status = "reused"
        return
    item.review_source_id = source.id
    item.review_task_id = task.id
    item.review_status = "imported"


def _existing_version(
    db: Session,
    *,
    repository_id: uuid.UUID,
    provider_item_id: str,
    provider_updated_at: datetime,
    comments_included: bool,
) -> GithubWorkItemVersion | None:
    return db.scalar(
        select(GithubWorkItemVersion).where(
            GithubWorkItemVersion.repository_id == repository_id,
            GithubWorkItemVersion.provider_item_id == provider_item_id,
            GithubWorkItemVersion.provider_updated_at == provider_updated_at,
            GithubWorkItemVersion.comments_included == comments_included,
        )
    )


def import_github_work_items(
    db: Session,
    *,
    settings: Settings,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    repository_id: uuid.UUID,
    state: Literal["all", "open", "closed"],
    item_type: Literal["all", "issue", "pull_request"],
    include_comments: bool,
    include_reviews: bool,
    limit: int,
) -> GithubWorkItemImportResult:
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
            message="只有已关联 GitHub remote 的仓库可以导入 Issue/PR",
        )

    base_url = settings.github_api_base_url.rstrip("/")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": settings.github_api_version,
        "User-Agent": "Knowledge-Atlas/0.1",
    }
    if settings.github_token is not None:
        headers["Authorization"] = f"Bearer {settings.github_token.get_secret_value()}"

    items: list[GithubWorkItemImportItem] = []
    limit = max(1, min(limit, MAX_GITHUB_WORK_ITEMS))
    fetch_count = min(max(limit * 3, limit + 1), 100)
    with httpx.Client(
        headers=headers,
        timeout=httpx.Timeout(settings.github_timeout_seconds, connect=10),
    ) as client:
        owner = quote(repository.remote_owner, safe="")
        name = quote(repository.remote_name, safe="")
        repository_payload = github_import._get_json(
            client, f"{base_url}/repos/{owner}/{name}"
        )
        github_import._update_provider_identity(
            db, repository=repository, payload=repository_payload
        )
        owner = quote(repository.remote_owner or "", safe="")
        name = quote(repository.remote_name or "", safe="")

        def append_result(
            item: GithubWorkItemImportItem,
            *,
            detected_type: str,
            provider_item_id: str,
            number: int,
            html_url: str,
        ) -> None:
            if detected_type == "pull_request" and include_reviews:
                _import_pull_review_activity(
                    db,
                    client=client,
                    settings=settings,
                    user_id=user_id,
                    project_id=project_id,
                    repository_id=repository.id,
                    base_url=base_url,
                    owner=owner,
                    name=name,
                    provider_pull_id=provider_item_id,
                    number=number,
                    html_url=html_url,
                    item=item,
                )
            items.append(item)

        list_kind = "pulls" if item_type == "pull_request" else "issues"
        remote_items = _get_json_array(
            client,
            f"{base_url}/repos/{owner}/{name}/{list_kind}",
            params={
                "state": state,
                "sort": "updated",
                "direction": "desc",
                "per_page": fetch_count,
            },
        )
        selected: list[tuple[dict[str, Any], str]] = []
        for payload in remote_items:
            detected_type = (
                "pull_request"
                if list_kind == "pulls" or isinstance(payload.get("pull_request"), dict)
                else "issue"
            )
            if item_type != "all" and detected_type != item_type:
                continue
            selected.append((payload, detected_type))
            if len(selected) >= limit:
                break
        truncated = (
            len(remote_items) >= fetch_count
            or len(selected) >= limit and len(remote_items) > len(selected)
        )

        for payload, detected_type in selected:
            fields = _required_item_fields(payload, forced_type=detected_type)
            canonical_payload = payload
            if detected_type == "pull_request" and list_kind == "pulls":
                canonical_payload = github_import._get_json(
                    client,
                    f"{base_url}/repos/{owner}/{name}/issues/{fields[1]}",
                )
                fields = _required_item_fields(
                    canonical_payload, forced_type=detected_type
                )
            (
                provider_item_id, number, detected_type, title, html_url,
                provider_updated_at, item_state,
            ) = fields
            existing = _existing_version(
                db,
                repository_id=repository.id,
                provider_item_id=provider_item_id,
                provider_updated_at=provider_updated_at,
                comments_included=include_comments,
            )
            if existing is not None:
                result_item = GithubWorkItemImportItem(
                    number=number,
                    item_type=detected_type,
                    title=title,
                    html_url=html_url,
                    source_id=existing.source_id,
                    task_id=existing.task_id,
                    status="reused",
                    comments_truncated=existing.comments_truncated,
                )
                append_result(
                    result_item,
                    detected_type=detected_type,
                    provider_item_id=provider_item_id,
                    number=number,
                    html_url=html_url,
                )
                continue

            detail = canonical_payload
            if detected_type == "pull_request":
                pull_request_detail = github_import._get_json(
                    client,
                    f"{base_url}/repos/{owner}/{name}/pulls/{number}",
                )
                detail = dict(canonical_payload)
                for key in ("head", "base", "merged"):
                    if key in pull_request_detail:
                        detail[key] = pull_request_detail[key]
            comments_count = canonical_payload.get("comments", 0)
            comments_count = (
                comments_count
                if isinstance(comments_count, int) and comments_count >= 0
                else 0
            )
            comments: list[dict[str, Any]] = []
            if include_comments and comments_count > 0:
                comments = _get_json_array(
                    client,
                    f"{base_url}/repos/{owner}/{name}/issues/{number}/comments",
                    params={"per_page": MAX_GITHUB_COMMENTS_PER_ITEM},
                )
            comments_truncated = include_comments and comments_count > len(comments)
            markdown = _render_markdown(
                detail,
                item_type=detected_type,
                number=number,
                title=title,
                html_url=html_url,
                comments=comments,
                comments_truncated=comments_truncated,
            )
            stem = "pull-request" if detected_type == "pull_request" else "issue"
            filename = f"{stem}-{number}.md"
            relative_path = f"github/{stem}s/{filename}"
            try:
                source, task, _ = ingestion.create_source_and_task_from_bytes(
                    db,
                    settings=settings,
                    user_id=user_id,
                    project_id=project_id,
                    filename=filename,
                    raw_content=markdown.encode("utf-8"),
                    source_type="markdown",
                    relative_path=relative_path,
                    repository_id=repository.id,
                )
            except AppError as exc:
                result_item = GithubWorkItemImportItem(
                    number=number,
                    item_type=detected_type,
                    title=title,
                    html_url=html_url,
                    status="skipped",
                    comments_truncated=comments_truncated,
                    error_code=exc.code,
                )
                append_result(
                    result_item,
                    detected_type=detected_type,
                    provider_item_id=provider_item_id,
                    number=number,
                    html_url=html_url,
                )
                continue

            version = GithubWorkItemVersion(
                user_id=user_id,
                project_id=project_id,
                repository_id=repository.id,
                source_id=source.id,
                task_id=task.id,
                provider_item_id=provider_item_id,
                number=number,
                item_type=detected_type,
                state=item_state,
                title=title,
                html_url=html_url,
                provider_updated_at=provider_updated_at,
                comments_count=comments_count if include_comments else 0,
                comments_included=include_comments,
                comments_truncated=comments_truncated,
            )
            db.add(version)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                winner = _existing_version(
                    db,
                    repository_id=repository.id,
                    provider_item_id=provider_item_id,
                    provider_updated_at=provider_updated_at,
                    comments_included=include_comments,
                )
                if winner is None:
                    raise
                result_item = GithubWorkItemImportItem(
                    number=number,
                    item_type=detected_type,
                    title=title,
                    html_url=html_url,
                    source_id=winner.source_id,
                    task_id=winner.task_id,
                    status="reused",
                    comments_truncated=winner.comments_truncated,
                )
                append_result(
                    result_item,
                    detected_type=detected_type,
                    provider_item_id=provider_item_id,
                    number=number,
                    html_url=html_url,
                )
                continue
            result_item = GithubWorkItemImportItem(
                number=number,
                item_type=detected_type,
                title=title,
                html_url=html_url,
                source_id=source.id,
                task_id=task.id,
                status="imported",
                comments_truncated=comments_truncated,
            )
            append_result(
                result_item,
                detected_type=detected_type,
                provider_item_id=provider_item_id,
                number=number,
                html_url=html_url,
            )

    db.add(repository)
    db.commit()
    return GithubWorkItemImportResult(
        repository_id=repository.id,
        imported_count=sum(item.status == "imported" for item in items),
        reused_count=sum(item.status == "reused" for item in items),
        skipped_count=sum(item.status == "skipped" for item in items),
        review_imported_count=sum(
            item.review_status == "imported" for item in items
        ),
        review_reused_count=sum(item.review_status == "reused" for item in items),
        review_skipped_count=sum(item.review_status == "skipped" for item in items),
        truncated=truncated,
        items=items,
    )
