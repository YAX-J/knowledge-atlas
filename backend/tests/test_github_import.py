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
    assert second.json()["reused_count"] == 0
    assert second.json()["unchanged_count"] == 2
    assert second.json()["snapshot_id"] == first.json()["snapshot_id"]
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
    assert {item["git_url"] for item in sources["items"]} == {
        f"https://github.com/example/demo/blob/{'a' * 40}/README.md",
        f"https://github.com/example/demo/blob/{'a' * 40}/src/App.java",
    }
    readme = next(
        item for item in sources["items"] if item["relative_path"] == "README.md"
    )
    detail = client.get(f"/api/v1/sources/{readme['id']}").json()
    assert detail["git_url"] == (
        f"https://github.com/example/demo/blob/{'a' * 40}/README.md"
    )
    snapshots = client.get(
        f"/api/v1/projects/{project_id}/repositories/{repository['id']}/snapshots"
    )
    assert snapshots.status_code == 200
    assert snapshots.json()["total"] == 1
    assert snapshots.json()["items"][0]["commit_sha"] == "a" * 40
    assert snapshots.json()["items"][0]["tree_sha"] == "t" * 40


def test_sync_github_incrementally_tracks_rename_delete_and_provider_identity(
    client: TestClient,
    monkeypatch,
) -> None:
    phase = 1
    blob_requests: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in {"/repos/example/demo", "/repos/example/renamed"}:
            return httpx.Response(200, json={
                "id": 42,
                "full_name": "Example/Renamed",
                "default_branch": "main",
            })
        if path.endswith("/commits/main"):
            sha = {1: "1", 2: "2", 3: "3"}[phase] * 40
            tree_sha = {1: "x", 2: "y", 3: "z"}[phase] * 40
            return httpx.Response(200, json={
                "sha": sha,
                "html_url": f"https://github.com/example/renamed/commit/{sha}",
                "commit": {
                    "message": f"phase {phase}",
                    "committer": {"date": "2026-10-20T08:00:00Z"},
                    "tree": {"sha": tree_sha},
                },
            })
        if path.endswith(f"/git/trees/{'x' * 40}"):
            return httpx.Response(200, json={
                "truncated": False,
                "tree": [
                    {"path": "A.md", "type": "blob", "sha": "same", "size": 4},
                    {"path": "gone.md", "type": "blob", "sha": "gone", "size": 7},
                    {"path": "keep.md", "type": "blob", "sha": "keep", "size": 7},
                ],
            })
        if path.endswith(f"/git/trees/{'y' * 40}"):
            return httpx.Response(200, json={
                "truncated": False,
                "tree": [
                    {"path": "B.md", "type": "blob", "sha": "same", "size": 4},
                    {"path": "keep.md", "type": "blob", "sha": "keep", "size": 7},
                    {"path": "new.md", "type": "blob", "sha": "new", "size": 6},
                ],
            })
        if path.endswith(f"/git/trees/{'z' * 40}"):
            return httpx.Response(200, json={
                "truncated": False,
                "tree": [
                    {"path": "B.md", "type": "blob", "sha": "same", "size": 4},
                    {"path": "gone.md", "type": "blob", "sha": "gone", "size": 7},
                    {"path": "keep.md", "type": "blob", "sha": "keep", "size": 7},
                ],
            })
        if "/git/blobs/" in path:
            blob_sha = path.rsplit("/", 1)[-1]
            blob_requests.append(blob_sha)
            content = {
                "same": b"# A\n",
                "gone": b"# Gone\n",
                "keep": b"# Keep\n",
                "new": b"# New\n",
            }[blob_sha]
            return httpx.Response(200, content=content)
        raise AssertionError(path)

    install_github_mock(monkeypatch, respond)
    project_id = create_project(client)
    repository = register_github(client, project_id)
    endpoint = (
        f"/api/v1/projects/{project_id}/repositories/"
        f"{repository['id']}/sync-github"
    )
    first = client.post(endpoint, json={})
    assert first.status_code == 200
    assert first.json()["imported_count"] == 3

    phase = 2
    second = client.post(endpoint, json={})
    assert second.status_code == 200
    payload = second.json()
    assert payload["commit_sha"] == "2" * 40
    assert payload["commit_url"].endswith("/commit/" + "2" * 40)
    assert (
        payload["imported_count"],
        payload["reused_count"],
        payload["unchanged_count"],
        payload["renamed_count"],
        payload["deleted_count"],
    ) == (1, 0, 1, 1, 1)
    assert payload["deletion_detection_complete"] is True
    assert {item["path"]: item["status"] for item in payload["items"]} == {
        "B.md": "renamed",
        "gone.md": "deleted",
        "keep.md": "unchanged",
        "new.md": "imported",
    }
    renamed = next(item for item in payload["items"] if item["status"] == "renamed")
    assert renamed["previous_path"] == "A.md"
    assert blob_requests == ["same", "gone", "keep", "new"]

    repositories = client.get(
        f"/api/v1/projects/{project_id}/repositories?page=1&page_size=20"
    ).json()
    stored_repository = repositories["items"][0]
    assert stored_repository["provider_repository_id"] == "42"
    assert stored_repository["remote_url"] == "https://github.com/example/renamed"
    assert stored_repository["name"] == "example/renamed"

    phase = 3
    third = client.post(endpoint, json={})
    assert third.status_code == 200
    assert third.json()["commit_sha"] == "3" * 40
    assert (
        third.json()["imported_count"],
        third.json()["reused_count"],
        third.json()["unchanged_count"],
        third.json()["deleted_count"],
    ) == (0, 1, 2, 1)
    assert next(
        item for item in third.json()["items"] if item["path"] == "gone.md"
    )["status"] == "reused"
    assert blob_requests == ["same", "gone", "keep", "new"]

    snapshots = client.get(
        f"/api/v1/projects/{project_id}/repositories/{repository['id']}/snapshots"
    ).json()
    assert snapshots["total"] == 3
    assert snapshots["items"][1]["renamed_count"] == 1
    assert snapshots["items"][1]["deleted_count"] == 1
    sources = client.get(
        f"/api/v1/projects/{project_id}/sources?page=1&page_size=20"
    ).json()["items"]
    by_path = {item["relative_path"]: item for item in sources}
    assert by_path["B.md"]["git_url"] == (
        f"https://github.com/example/renamed/blob/{'3' * 40}/B.md"
    )
    assert by_path["new.md"]["git_url"] == (
        f"https://github.com/example/renamed/blob/{'2' * 40}/new.md"
    )


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
    assert response.json()["deletion_detection_complete"] is False
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
