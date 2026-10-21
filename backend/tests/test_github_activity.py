from collections.abc import Callable

import httpx
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
) -> None:
    settings = Settings(
        _env_file=None,
        github_api_base_url="https://api.github.test",
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
        raise AssertionError(path)

    install_github_mock(monkeypatch, respond)
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
    assert [item["item_type"] for item in payload["items"]] == [
        "issue", "pull_request",
    ]
    sources = client.get(
        f"/api/v1/projects/{project_id}/sources?page=1&page_size=20"
    ).json()
    assert sources["total"] == 2
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

    request_count = len(requests)
    second = client.post(endpoint, json={})
    assert second.status_code == 200
    assert (second.json()["imported_count"], second.json()["reused_count"]) == (0, 2)
    assert requests[request_count:] == [
        "/repos/example/demo", "/repos/example/demo/issues",
    ]
    assert client.get(
        f"/api/v1/projects/{project_id}/sources?page=1&page_size=20"
    ).json()["total"] == 2

    request_count = len(requests)
    pull_only = client.post(endpoint, json={"item_type": "pull_request"})
    assert pull_only.status_code == 200
    assert (pull_only.json()["imported_count"], pull_only.json()["reused_count"]) == (0, 1)
    assert requests[request_count:] == [
        "/repos/example/demo", "/repos/example/demo/pulls",
        "/repos/example/demo/issues/8",
    ]

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
    ).json()["total"] == 3


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
