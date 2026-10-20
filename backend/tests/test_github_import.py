from collections.abc import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.routes import repositories as repository_routes
from app.core.config import Settings
from app.services import github_import


def create_project(client: TestClient) -> str:
    response = client.post(
        "/api/v1/projects",
        json={"name": "GitHub import", "description": ""},
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
    token: str | None = None,
    max_upload_bytes: int = 10 * 1024 * 1024,
) -> None:
    settings = Settings(
        _env_file=None,
        github_api_base_url="https://api.github.test",
        github_token=token,
        max_upload_bytes=max_upload_bytes,
    )
    monkeypatch.setattr(repository_routes, "get_settings", lambda: settings)
    original_client = httpx.Client
    monkeypatch.setattr(
        github_import.httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(responder), **kwargs
        ),
    )


def test_sync_github_imports_reuses_and_skips_supported_files(
    client: TestClient,
    monkeypatch,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path == "/repos/example/demo":
            return httpx.Response(200, json={"default_branch": "main"})
        if path == "/repos/example/demo/commits/main":
            return httpx.Response(200, json={
                "sha": "a" * 40,
                "commit": {"tree": {"sha": "t" * 40}},
            })
        if path == f"/repos/example/demo/git/trees/{'t' * 40}":
            assert request.url.params["recursive"] == "1"
            return httpx.Response(200, json={
                "truncated": False,
                "tree": [
                    {"path": "src/App.java", "type": "blob", "sha": "java", "size": 22},
                    {"path": "assets/logo.png", "type": "blob", "sha": "png", "size": 12},
                    {"path": "README.md", "type": "blob", "sha": "readme", "size": 8},
                    {"path": "empty.md", "type": "blob", "sha": "empty", "size": 0},
                ],
            })
        if path.endswith("/git/blobs/readme"):
            assert request.headers["accept"] == "application/vnd.github.raw+json"
            return httpx.Response(200, content=b"# Demo\n")
        if path.endswith("/git/blobs/java"):
            return httpx.Response(200, content=b"class App {}\n")
        raise AssertionError(path)

    install_github_mock(monkeypatch, respond, token="private-token")
    project_id = create_project(client)
    repository = register_github(client, project_id)
    endpoint = (
        f"/api/v1/projects/{project_id}/repositories/"
        f"{repository['id']}/sync-github"
    )

    first = client.post(endpoint, json={})
    assert first.status_code == 200
    payload = first.json()
    assert payload["ref"] == "main"
    assert payload["commit_sha"] == "a" * 40
    assert (payload["imported_count"], payload["reused_count"], payload["skipped_count"]) == (2, 0, 1)
    assert [item["path"] for item in payload["items"]] == [
        "README.md", "empty.md", "src/App.java",
    ]
    assert payload["items"][1]["error_code"] == "SOURCE_EMPTY"
    assert all(
        request.headers.get("authorization") == "Bearer private-token"
        for request in requests
    )

    second = client.post(endpoint, json={})
    assert second.status_code == 200
    assert second.json()["imported_count"] == 0
    assert second.json()["reused_count"] == 2
    sources = client.get(
        f"/api/v1/projects/{project_id}/sources?page=1&page_size=20"
    ).json()
    assert sources["total"] == 2
    assert {item["relative_path"] for item in sources["items"]} == {
        "README.md", "src/App.java",
    }
    assert {item["repository_id"] for item in sources["items"]} == {
        repository["id"]
    }


def test_sync_github_supports_ref_and_reports_truncation(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(github_import, "MAX_GITHUB_IMPORT_FILES", 1)

    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode("ascii").split("?", 1)[0]
        if path == "/repos/example/demo":
            return httpx.Response(200, json={"default_branch": "main"})
        if path == "/repos/example/demo/commits/release%2F1.0":
            return httpx.Response(200, json={
                "sha": "b" * 40,
                "commit": {"tree": {"sha": "u" * 40}},
            })
        if path == f"/repos/example/demo/git/trees/{'u' * 40}":
            return httpx.Response(200, json={
                "truncated": False,
                "tree": [
                    {"path": "A.md", "type": "blob", "sha": "a", "size": 4},
                    {"path": "B.md", "type": "blob", "sha": "b", "size": 4},
                ],
            })
        if path.endswith("/git/blobs/a"):
            return httpx.Response(200, content=b"# A\n")
        raise AssertionError(path)

    install_github_mock(monkeypatch, respond)
    project_id = create_project(client)
    repository = register_github(client, project_id)
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository['id']}/sync-github",
        json={"ref": " release/1.0 "},
    )
    assert response.status_code == 200
    assert response.json()["ref"] == "release/1.0"
    assert response.json()["truncated"] is True
    assert [item["path"] for item in response.json()["items"]] == ["A.md"]


def test_sync_github_rejects_local_only_repository(
    client: TestClient,
    monkeypatch,
) -> None:
    project_id = create_project(client)
    repository = client.post(
        f"/api/v1/projects/{project_id}/repositories/resolve",
        json={"name": "local", "kind": "local_folder"},
    ).json()
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository['id']}/sync-github",
        json={},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GITHUB_REPOSITORY_REQUIRED"


def test_sync_github_streams_and_skips_oversized_blob(
    client: TestClient,
    monkeypatch,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/example/demo":
            return httpx.Response(200, json={"default_branch": "main"})
        if path == "/repos/example/demo/commits/main":
            return httpx.Response(200, json={
                "sha": "c" * 40,
                "commit": {"tree": {"sha": "v" * 40}},
            })
        if path == f"/repos/example/demo/git/trees/{'v' * 40}":
            return httpx.Response(200, json={
                "truncated": False,
                "tree": [
                    {"path": "oversized.md", "type": "blob", "sha": "large", "size": 4},
                ],
            })
        if path.endswith("/git/blobs/large"):
            return httpx.Response(200, content=b"12345")
        raise AssertionError(path)

    install_github_mock(monkeypatch, respond, max_upload_bytes=4)
    project_id = create_project(client)
    repository = register_github(client, project_id)
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository['id']}/sync-github",
        json={},
    )
    assert response.status_code == 200
    assert response.json()["skipped_count"] == 1
    assert response.json()["items"][0]["error_code"] == "SOURCE_TOO_LARGE"
    assert client.get(
        f"/api/v1/projects/{project_id}/sources?page=1&page_size=20"
    ).json()["total"] == 0


@pytest.mark.parametrize("provider_status", [403, 429])
def test_sync_github_maps_rate_limit_failures(
    client: TestClient,
    monkeypatch,
    provider_status: int,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(provider_status, json={"message": "rate limited"})

    install_github_mock(monkeypatch, respond)
    project_id = create_project(client)
    repository = register_github(client, project_id)
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository['id']}/sync-github",
        json={},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "GITHUB_RATE_LIMITED"


@pytest.mark.parametrize("provider_status", [404, 422])
def test_sync_github_maps_missing_repository_or_ref(
    client: TestClient,
    monkeypatch,
    provider_status: int,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(provider_status, json={"message": "not found"})

    install_github_mock(monkeypatch, respond)
    project_id = create_project(client)
    repository = register_github(client, project_id)
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/{repository['id']}/sync-github",
        json={"ref": "missing-ref"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "GITHUB_REPOSITORY_UNAVAILABLE"
