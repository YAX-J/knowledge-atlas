import pytest
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
    assert source["relative_path"] is None
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


def test_folder_relative_path_is_normalized_exposed_and_kept_on_reuse(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    content = b"package example;\nclass Decision {}\n"
    first = client.post(
        f"/api/v1/projects/{project_id}/sources",
        data={"source_type": "java", "relative_path": "sample\\src\\Decision.java"},
        files={"file": ("Decision.java", content, "text/x-java-source")},
    )
    assert first.status_code == 202

    source = client.get(f"/api/v1/sources/{first.json()['source_id']}").json()
    assert source["relative_path"] == "sample/src/Decision.java"
    listed = client.get(f"/api/v1/projects/{project_id}/sources").json()["items"]
    assert listed[0]["relative_path"] == "sample/src/Decision.java"

    reused = client.post(
        f"/api/v1/projects/{project_id}/sources",
        data={"source_type": "java", "relative_path": "renamed/Decision.java"},
        files={"file": ("Decision.java", content, "text/x-java-source")},
    )
    assert reused.status_code == 202
    assert reused.json()["source_id"] == first.json()["source_id"]
    source = client.get(f"/api/v1/sources/{first.json()['source_id']}").json()
    assert source["relative_path"] == "sample/src/Decision.java"


@pytest.mark.parametrize(
    "relative_path",
    [
        "../decision.md",
        "/docs/decision.md",
        "C:/docs/decision.md",
        "docs/other.md",
        "docs//decision.md",
        f"{'a' * 1013}/decision.md",
    ],
)
def test_rejects_invalid_relative_path(
    client: TestClient, relative_path: str
) -> None:
    project_id = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/sources",
        data={"relative_path": relative_path},
        files={"file": ("decision.md", b"# Decision", "text/markdown")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SOURCE_PATH_INVALID"

