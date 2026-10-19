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
    finally:
        app.dependency_overrides.pop(get_current_user_id)
