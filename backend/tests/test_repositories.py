import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user_id
from app.main import app
from tests.test_sources import create_project


def resolve_repository(
    client: TestClient, project_id: str, name: str = "commerce-core"
) -> dict:
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/resolve",
        json={"name": name, "kind": "local_folder"},
    )
    assert response.status_code == 200
    return response.json()


def resolve_github_repository(
    client: TestClient,
    project_id: str,
    remote_url: str,
    local_repository_id: str | None = None,
):
    payload = {"remote_url": remote_url}
    if local_repository_id is not None:
        payload["local_repository_id"] = local_repository_id
    return client.post(
        f"/api/v1/projects/{project_id}/repositories/resolve-github",
        json=payload,
    )


def test_resolve_repository_is_idempotent_and_listed(client: TestClient) -> None:
    project_id = create_project(client)
    first = resolve_repository(client, project_id, " commerce-core ")
    second = resolve_repository(client, project_id, "commerce-core")

    assert second == first
    assert first["project_id"] == project_id
    assert first["name"] == "commerce-core"
    assert first["kind"] == "local_folder"

    response = client.get(f"/api/v1/projects/{project_id}/repositories")
    assert response.status_code == 200
    assert response.json() == {
        "items": [first], "page": 1, "page_size": 20, "total": 1
    }

    longest = resolve_repository(client, project_id, f" {'a' * 255} ")
    assert longest["name"] == "a" * 255


@pytest.mark.parametrize("name", ["", "   ", ".", "..", "a/b", "a\\b", "a\nb"])
def test_repository_name_must_be_one_folder_name(
    client: TestClient, name: str
) -> None:
    response = client.post(
        f"/api/v1/projects/{create_project(client)}/repositories/resolve",
        json={"name": name},
    )
    assert response.status_code == 422


def test_repository_kind_is_currently_local_folder_only(
    client: TestClient,
) -> None:
    response = client.post(
        f"/api/v1/projects/{create_project(client)}/repositories/resolve",
        json={"name": "commerce-core", "kind": "git"},
    )
    assert response.status_code == 422


def test_resolve_github_repository_normalizes_and_reuses_remote(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    first = resolve_github_repository(
        client,
        project_id,
        "https://github.com/OpenAI/Knowledge-Atlas.git/",
    )
    second = resolve_github_repository(
        client,
        project_id,
        "git@github.com:openai/knowledge-atlas.git",
    )

    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()
    repository = first.json()
    assert repository["kind"] == "git_remote"
    assert repository["name"] == "openai/knowledge-atlas"
    assert repository["provider"] == "github"
    assert repository["remote_owner"] == "openai"
    assert repository["remote_name"] == "knowledge-atlas"
    assert repository["remote_url"] == (
        "https://github.com/openai/knowledge-atlas"
    )


def test_github_remote_can_attach_to_local_repository(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    local = resolve_repository(client, project_id, "knowledge-atlas")

    response = resolve_github_repository(
        client,
        project_id,
        "ssh://git@github.com/example/knowledge-atlas.git",
        local["id"],
    )

    assert response.status_code == 200
    repository = response.json()
    assert repository["id"] == local["id"]
    assert repository["kind"] == "local_folder"
    assert repository["remote_url"] == (
        "https://github.com/example/knowledge-atlas"
    )
    repeated = resolve_github_repository(
        client,
        project_id,
        "git@github.com:example/knowledge-atlas.git",
        local["id"],
    )
    assert repeated.status_code == 200
    assert repeated.json() == repository
    listed = client.get(
        f"/api/v1/projects/{project_id}/repositories"
    ).json()
    assert listed["total"] == 1
    assert listed["items"] == [repository]


def test_github_remote_rejects_duplicate_and_conflicting_links(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    registered = resolve_github_repository(
        client, project_id, "https://github.com/example/registered"
    ).json()
    local = resolve_repository(client, project_id, "local")

    non_local = resolve_github_repository(
        client,
        project_id,
        registered["remote_url"],
        registered["id"],
    )
    assert non_local.status_code == 409
    assert non_local.json()["error"]["code"] == "SOURCE_REPOSITORY_NOT_LOCAL"

    duplicate = resolve_github_repository(
        client,
        project_id,
        registered["remote_url"],
        local["id"],
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == (
        "GITHUB_REPOSITORY_ALREADY_REGISTERED"
    )

    linked = resolve_github_repository(
        client,
        project_id,
        "https://github.com/example/first",
        local["id"],
    )
    assert linked.status_code == 200
    conflict = resolve_github_repository(
        client,
        project_id,
        "https://github.com/example/second",
        local["id"],
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == (
        "SOURCE_REPOSITORY_REMOTE_CONFLICT"
    )


@pytest.mark.parametrize(
    "remote_url",
    [
        "http://github.com/example/repository",
        "https://gitlab.com/example/repository",
        "https://token@github.com/example/repository",
        "https://github.com/example/repository?token=secret",
        "github.com/example/repository",
    ],
)
def test_github_remote_rejects_unsupported_or_credentialed_urls(
    client: TestClient,
    remote_url: str,
) -> None:
    response = resolve_github_repository(
        client, create_project(client), remote_url
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "GITHUB_REMOTE_INVALID"


def test_repository_project_and_user_boundaries(client: TestClient) -> None:
    first_project = create_project(client)
    second_project = create_project(client)
    repository = resolve_repository(client, first_project)

    assert client.get(
        f"/api/v1/projects/{second_project}/repositories"
    ).json()["total"] == 0
    response = client.post(
        f"/api/v1/projects/{uuid.uuid4()}/repositories/resolve",
        json={"name": "missing"},
    )
    assert response.status_code == 404
    wrong_project_remote = resolve_github_repository(
        client,
        second_project,
        "https://github.com/example/commerce-core",
        repository["id"],
    )
    assert wrong_project_remote.status_code == 404
    assert wrong_project_remote.json()["error"]["code"] == (
        "SOURCE_REPOSITORY_NOT_FOUND"
    )

    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(
            f"/api/v1/projects/{first_project}/repositories"
        ).status_code == 404
        upload = client.post(
            f"/api/v1/projects/{first_project}/sources",
            data={
                "repository_id": repository["id"],
                "relative_path": "src/App.java",
            },
            files={
                "file": ("App.java", b"class App {}", "text/x-java-source")
            },
        )
        assert upload.status_code == 404
        assert resolve_github_repository(
            client,
            first_project,
            "https://github.com/example/commerce-core",
        ).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)
