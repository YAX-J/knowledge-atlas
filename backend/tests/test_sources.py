from fastapi.testclient import TestClient


def create_project(client: TestClient) -> str:
    response = client.post(
        "/api/v1/projects",
        json={"name": "知识导入测试", "description": ""},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_upload_markdown_creates_source_and_queued_task(client: TestClient) -> None:
    project_id = create_project(client)
    content = "# 事件一致性\n\n事务提交后发布领域事件。\n"

    upload_response = client.post(
        f"/api/v1/projects/{project_id}/sources",
        files={"file": ("decision.md", content.encode("utf-8"), "text/markdown")},
    )

    assert upload_response.status_code == 202
    upload = upload_response.json()
    assert upload["status"] == "queued"

    source_response = client.get(f"/api/v1/sources/{upload['source_id']}")
    assert source_response.status_code == 200
    source = source_response.json()
    assert source["original_name"] == "decision.md"
    assert source["line_count"] == 3
    assert source["content_preview"] == content
    assert len(source["content_sha256"]) == 64

    task_response = client.get(f"/api/v1/tasks/{upload['task_id']}")
    assert task_response.status_code == 200
    task = task_response.json()
    assert task["source_id"] == upload["source_id"]
    assert task["status"] == "queued"
    assert task["stage"] == "uploaded"
    assert task["progress"] == 0


def test_rejects_unsupported_file_type(client: TestClient) -> None:
    project_id = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/sources",
        files={"file": ("secret.exe", b"not markdown", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_SOURCE_TYPE"


def test_rejects_empty_markdown(client: TestClient) -> None:
    project_id = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/sources",
        files={"file": ("empty.md", b"\n  \n", "text/markdown")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SOURCE_EMPTY"

