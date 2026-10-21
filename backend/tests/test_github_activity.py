import json
from collections.abc import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.routes import repositories as repository_routes
from app.core.config import Settings
from app.services import github_activity
from app.services.source_links import github_line_url


def create_project(client: TestClient) -> str:
    response = client.post(
        "/api/v1/projects",
        json={"name": "GitHub activity", "description": ""},
    )
    assert response.status_code == 201
    return response.json()["id"]


def register_github(client: TestClient, project_id: str) -> dict:
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/resolve-github",
        json={"remote_url": "https://github.com/example/demo"},
    )
    assert response.status_code == 200
    return response.json()


def install_github_mock(
    monkeypatch,
    responder: Callable[[httpx.Request], httpx.Response],
    *,
    max_upload_bytes: int = 10 * 1024 * 1024,
    github_token: str | None = None,
) -> None:
    settings = Settings(
        _env_file=None,
        github_api_base_url="https://api.github.test",
        github_graphql_url="https://api.github.test/graphql",
        github_token=github_token,
        max_upload_bytes=max_upload_bytes,
    )
    monkeypatch.setattr(repository_routes, "get_settings", lambda: settings)
    original_client = httpx.Client
    monkeypatch.setattr(
        github_activity.httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(responder), **kwargs
        ),
    )


def test_import_github_issues_and_pull_requests_as_versioned_sources(
    client: TestClient,
    monkeypatch,
) -> None:
    requests: list[str] = []
    issue_version = {
        "updated_at": "2026-10-21T08:00:00Z",
        "body": "Retries must preserve evidence.",
    }
    review_version = {
        "updated_at": "2026-10-21T09:30:00Z",
        "body": "Please keep the retry budget bounded.",
    }
    thread_version = {"resolved": True}

    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        requests.append(path)
        if path == "/repos/example/demo":
            return httpx.Response(200, json={
                "id": 42,
                "full_name": "Example/Demo",
            })
        if path == "/repos/example/demo/issues":
            assert request.url.params["state"] == "all"
            return httpx.Response(200, json=[
                {
                    "id": 101,
                    "number": 7,
                    "title": "Document retry behavior",
                    "html_url": "https://github.com/example/demo/issues/7",
                    "state": "open",
                    "user": {"login": "ada"},
                    "created_at": "2026-10-20T08:00:00Z",
                    "updated_at": issue_version["updated_at"],
                    "body": issue_version["body"],
                    "comments": 1,
                    "labels": [{"name": "decision"}],
                },
                {
                    "id": 202,
                    "number": 8,
                    "title": "Add bounded retries",
                    "html_url": "https://github.com/example/demo/pull/8",
                    "state": "closed",
                    "user": {"login": "grace"},
                    "created_at": "2026-10-20T09:00:00Z",
                    "updated_at": "2026-10-21T09:00:00Z",
                    "body": "Implements the retry decision.",
                    "comments": 0,
                    "pull_request": {"url": "https://api.github.test/pulls/8"},
                    "labels": [],
                },
            ])
        if path == "/repos/example/demo/pulls":
            return httpx.Response(200, json=[{
                "id": 999,
                "number": 8,
                "title": "Add bounded retries",
                "html_url": "https://github.com/example/demo/pull/8",
                "state": "closed",
                "user": {"login": "grace"},
                "created_at": "2026-10-20T09:00:00Z",
                "updated_at": "2026-10-21T09:00:00Z",
                "body": "Implements the retry decision.",
            }])
        if path == "/repos/example/demo/issues/8":
            return httpx.Response(200, json={
                "id": 202,
                "number": 8,
                "title": "Add bounded retries",
                "html_url": "https://github.com/example/demo/pull/8",
                "state": "closed",
                "user": {"login": "grace"},
                "created_at": "2026-10-20T09:00:00Z",
                "updated_at": "2026-10-21T09:00:00Z",
                "body": "Implements the retry decision.",
                "comments": 0,
                "labels": [],
            })
        if path == "/repos/example/demo/issues/7/comments":
            return httpx.Response(200, json=[{
                "id": 301,
                "user": {"login": "linus"},
                "created_at": "2026-10-21T08:30:00Z",
                "body": "Keep the attempt counter visible.",
            }])
        if path == "/repos/example/demo/pulls/8":
            return httpx.Response(200, json={
                "id": 202,
                "number": 8,
                "title": "Add bounded retries",
                "html_url": "https://github.com/example/demo/pull/8",
                "state": "closed",
                "user": {"login": "grace"},
                "created_at": "2026-10-20T09:00:00Z",
                "updated_at": "2026-10-21T09:00:00Z",
                "body": "Implements the retry decision.",
                "comments": 0,
                "head": {"label": "example:retry"},
                "base": {"label": "example:main"},
                "merged": True,
                "labels": [],
            })
        if path == "/repos/example/demo/pulls/8/reviews":
            return httpx.Response(
                200,
                headers={
                    "Link": (
                        '<https://api.github.test/repos/example/demo/pulls/8/'
                        'reviews?per_page=20&page=2>; rel="next"'
                    )
                },
                json=[{
                    "id": 401,
                    "user": {"login": "margaret"},
                    "body": review_version["body"],
                    "state": "CHANGES_REQUESTED",
                    "html_url": (
                        "https://github.com/example/demo/pull/8#pullrequestreview-401"
                    ),
                    "submitted_at": review_version["updated_at"],
                    "commit_id": "abc123",
                }],
            )
        if path == "/repos/example/demo/pulls/8/comments":
            return httpx.Response(
                200,
                headers={
                    "Link": (
                        '<https://api.github.test/repos/example/demo/pulls/8/'
                        'comments?per_page=20&page=2>; rel="next"'
                    )
                },
                json=[{
                    "id": 402,
                    "in_reply_to_id": 399,
                    "user": {"login": "grace"},
                    "path": "backend/retry.py",
                    "line": 17,
                    "body": "The counter is now capped.",
                    "created_at": "2026-10-21T09:40:00Z",
                    "updated_at": "2026-10-21T09:41:00Z",
                    "html_url": (
                        "https://github.com/example/demo/pull/8#discussion_r402"
                    ),
                }],
            )
        if path == "/graphql" and request.method == "POST":
            graphql_request = json.loads(request.content)
            assert graphql_request["variables"] == {
                "owner": "example",
                "name": "demo",
                "number": 8,
                "threadLimit": 20,
                "commentLimit": 20,
            }
            assert request.headers["authorization"] == "Bearer test-token"
            return httpx.Response(200, json={
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "totalCount": 1,
                                "pageInfo": {"hasNextPage": False},
                                "nodes": [{
                                    "id": "PRRT_thread_1",
                                    "isResolved": thread_version["resolved"],
                                    "isOutdated": False,
                                    "isCollapsed": thread_version["resolved"],
                                    "resolvedBy": (
                                        {"login": "margaret"}
                                        if thread_version["resolved"] else None
                                    ),
                                    "path": "backend/retry.py",
                                    "line": 17,
                                    "originalLine": 17,
                                    "startLine": None,
                                    "originalStartLine": None,
                                    "diffSide": "RIGHT",
                                    "startDiffSide": None,
                                    "subjectType": "LINE",
                                    "comments": {
                                        "totalCount": 2,
                                        "pageInfo": {"hasNextPage": True},
                                        "nodes": [{"databaseId": 402}],
                                    },
                                }],
                            }
                        }
                    }
                }
            })
        raise AssertionError(path)

    install_github_mock(monkeypatch, respond, github_token="test-token")
    project_id = create_project(client)
    repository = register_github(client, project_id)
    endpoint = (
        f"/api/v1/projects/{project_id}/repositories/{repository['id']}"
        "/import-github-work-items"
    )

    first = client.post(endpoint, json={})
    assert first.status_code == 200
    payload = first.json()
    assert (
        payload["imported_count"],
        payload["reused_count"],
        payload["skipped_count"],
    ) == (2, 0, 0)
    assert (
        payload["review_imported_count"],
        payload["review_reused_count"],
        payload["review_skipped_count"],
    ) == (1, 0, 0)
    assert [item["item_type"] for item in payload["items"]] == [
        "issue", "pull_request",
    ]
    sources = client.get(
        f"/api/v1/projects/{project_id}/sources?page=1&page_size=20"
    ).json()
    assert sources["total"] == 3
    urls = {item["git_url"] for item in sources["items"]}
    assert urls == {
        "https://github.com/example/demo/issues/7",
        "https://github.com/example/demo/pull/8",
    }
    issue = next(item for item in sources["items"] if item["git_url"].endswith("/7"))
    detail = client.get(f"/api/v1/sources/{issue['id']}").json()
    assert "Keep the attempt counter visible." in detail["content_preview"]
    assert detail["relative_path"] == "github/issues/issue-7.md"
    assert github_line_url(detail["git_url"], start_line=1, end_line=3) == detail["git_url"]
    assert github_line_url(
        "https://github.com/example/demo/blob/abc/docs/issues/note.md",
        start_line=2,
        end_line=4,
    ).endswith("#L2-L4")
    review_source = next(
        item for item in sources["items"]
        if item["relative_path"] == (
            "github/pull-request-reviews/pull-request-8-reviews.md"
        )
    )
    review_detail = client.get(f"/api/v1/sources/{review_source['id']}").json()
    assert "Please keep the retry budget bounded." in review_detail["content_preview"]
    assert "`backend/retry.py:17`" in review_detail["content_preview"]
    assert "Reply to review comment: 399" in review_detail["content_preview"]
    assert "RESOLVED thread `PRRT_thread_1`" in review_detail["content_preview"]
    assert "Resolved by: @margaret" in review_detail["content_preview"]
    assert "Review comment IDs: 402" in review_detail["content_preview"]
    pull_item = next(
        item for item in payload["items"] if item["item_type"] == "pull_request"
    )
    assert pull_item["review_source_id"] == review_source["id"]
    assert pull_item["reviews_count"] == 1
    assert pull_item["review_comments_count"] == 1
    assert pull_item["reviews_truncated"] is True
    assert pull_item["review_comments_truncated"] is True
    assert pull_item["review_threads_status"] == "included"
    assert pull_item["review_threads_count"] == 1
    assert pull_item["resolved_review_threads_count"] == 1
    assert pull_item["review_threads_truncated"] is True

    request_count = len(requests)
    second = client.post(endpoint, json={})
    assert second.status_code == 200
    second_payload = second.json()
    assert (second_payload["imported_count"], second_payload["reused_count"]) == (0, 2)
    assert (
        second_payload["review_imported_count"],
        second_payload["review_reused_count"],
    ) == (0, 1)
    assert requests[request_count:] == [
        "/repos/example/demo", "/repos/example/demo/issues",
        "/repos/example/demo/pulls/8/reviews",
        "/repos/example/demo/pulls/8/comments",
        "/graphql",
    ]
    assert client.get(
        f"/api/v1/projects/{project_id}/sources?page=1&page_size=20"
    ).json()["total"] == 3

    request_count = len(requests)
    pull_only = client.post(endpoint, json={"item_type": "pull_request"})
    assert pull_only.status_code == 200
    assert (pull_only.json()["imported_count"], pull_only.json()["reused_count"]) == (0, 1)
    assert requests[request_count:] == [
        "/repos/example/demo", "/repos/example/demo/pulls",
        "/repos/example/demo/issues/8",
        "/repos/example/demo/pulls/8/reviews",
        "/repos/example/demo/pulls/8/comments",
        "/graphql",
    ]

    request_count = len(requests)
    without_reviews = client.post(
        endpoint,
        json={"item_type": "pull_request", "include_reviews": False},
    )
    assert without_reviews.status_code == 200
    assert without_reviews.json()["items"][0]["review_status"] == "not_requested"
    assert requests[request_count:] == [
        "/repos/example/demo", "/repos/example/demo/pulls",
        "/repos/example/demo/issues/8",
    ]

    review_version.update({
        "updated_at": "2026-10-21T09:50:00Z",
        "body": "Please keep the retry budget bounded and observable.",
    })
    review_updated = client.post(endpoint, json={"item_type": "pull_request"})
    assert review_updated.status_code == 200
    assert (
        review_updated.json()["imported_count"],
        review_updated.json()["reused_count"],
    ) == (0, 1)
    assert (
        review_updated.json()["review_imported_count"],
        review_updated.json()["review_reused_count"],
    ) == (1, 0)
    assert client.get(
        f"/api/v1/projects/{project_id}/sources?page=1&page_size=20"
    ).json()["total"] == 4

    thread_version["resolved"] = False
    thread_updated = client.post(endpoint, json={"item_type": "pull_request"})
    assert thread_updated.status_code == 200
    assert (
        thread_updated.json()["review_imported_count"],
        thread_updated.json()["review_reused_count"],
    ) == (1, 0)
    updated_pull = thread_updated.json()["items"][0]
    assert updated_pull["resolved_review_threads_count"] == 0
    assert client.get(
        f"/api/v1/projects/{project_id}/sources?page=1&page_size=20"
    ).json()["total"] == 5

    issue_version.update({
        "updated_at": "2026-10-21T10:00:00Z",
        "body": "Retries must preserve durable evidence.",
    })
    updated = client.post(endpoint, json={})
    assert updated.status_code == 200
    assert (updated.json()["imported_count"], updated.json()["reused_count"]) == (1, 1)
    updated_issue = next(
        item for item in updated.json()["items"] if item["item_type"] == "issue"
    )
    assert updated_issue["source_id"] != issue["id"]
    assert client.get(
        f"/api/v1/projects/{project_id}/sources?page=1&page_size=20"
    ).json()["total"] == 6


@pytest.mark.parametrize("github_token", [None, "", "   "])
def test_review_thread_state_without_token_is_reported_without_graphql(
    client: TestClient,
    monkeypatch,
    github_token: str | None,
) -> None:
    requests: list[tuple[str, str]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        assert "authorization" not in request.headers
        path = request.url.path
        if path == "/repos/example/demo":
            return httpx.Response(200, json={"id": 42, "full_name": "example/demo"})
        if path == "/repos/example/demo/pulls":
            return httpx.Response(200, json=[{
                "id": 202,
                "number": 8,
                "title": "Bounded review threads",
                "html_url": "https://github.com/example/demo/pull/8",
                "state": "open",
                "user": {"login": "grace"},
                "created_at": "2026-10-21T09:00:00Z",
                "updated_at": "2026-10-21T09:00:00Z",
                "body": "Thread state is optional.",
            }])
        if path == "/repos/example/demo/issues/8":
            return httpx.Response(200, json={
                "id": 202,
                "number": 8,
                "title": "Bounded review threads",
                "html_url": "https://github.com/example/demo/pull/8",
                "state": "open",
                "user": {"login": "grace"},
                "created_at": "2026-10-21T09:00:00Z",
                "updated_at": "2026-10-21T09:00:00Z",
                "body": "Thread state is optional.",
                "comments": 0,
                "labels": [],
            })
        if path == "/repos/example/demo/pulls/8":
            return httpx.Response(200, json={"head": {}, "base": {}, "merged": False})
        if path in {
            "/repos/example/demo/pulls/8/reviews",
            "/repos/example/demo/pulls/8/comments",
        }:
            return httpx.Response(200, json=[])
        raise AssertionError(path)

    install_github_mock(monkeypatch, respond, github_token=github_token)
    project_id = create_project(client)
    repository = register_github(client, project_id)
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository['id']}"
        "/import-github-work-items",
        json={"item_type": "pull_request"},
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["review_status"] == "imported"
    assert item["review_threads_status"] == "token_required"
    assert item["review_threads_count"] == 0
    assert not any(path == "/graphql" for _, path in requests)


def test_import_github_work_items_rejects_local_only_repository(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    repository = client.post(
        f"/api/v1/projects/{project_id}/repositories/resolve",
        json={"name": "local", "kind": "local_folder"},
    ).json()
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository['id']}"
        "/import-github-work-items",
        json={},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GITHUB_REPOSITORY_REQUIRED"
