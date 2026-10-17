from fastapi.testclient import TestClient


def test_create_list_and_get_project(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/projects",
        json={"name": "  订单状态机  ", "description": "领域事件实验"},
    )

    assert create_response.status_code == 201
    project = create_response.json()
    assert project["name"] == "订单状态机"

    list_response = client.get("/api/v1/projects")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["id"] == project["id"]

    detail_response = client.get(f"/api/v1/projects/{project['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["description"] == "领域事件实验"


def test_blank_project_name_uses_standard_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects", json={"name": "   ", "description": ""}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_REQUEST"
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]


def test_missing_project_is_scoped_as_not_found(client: TestClient) -> None:
    response = client.get(
        "/api/v1/projects/00000000-0000-0000-0000-000000000099"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"

