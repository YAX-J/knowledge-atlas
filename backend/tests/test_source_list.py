import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_id
from app.main import app
from app.models.domain import ProcessingTask, SourceDocument, TaskStatus, utc_now
from tests.test_sources import create_project


def upload(client: TestClient, project_id: str, content: bytes) -> dict:
    response = client.post(
        f"/api/v1/projects/{project_id}/sources",
        files={"file": ("note.md", content, "text/markdown")},
    )
    assert response.status_code == 202
    return response.json()


def test_source_list_pagination_and_latest_task(client: TestClient, db_session: Session) -> None:
    project_id = create_project(client)
    assert client.get(f"/api/v1/projects/{project_id}/sources").json()["total"] == 0
    first = upload(client, project_id, b"# First")
    second = upload(client, project_id, b"# Second")
    client.post(f"/api/v1/tasks/{second['task_id']}/run")
    response = client.get(f"/api/v1/projects/{project_id}/sources?page_size=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 1
    item = data["items"][0]
    assert item["id"] == second["source_id"]
    assert item["project_id"] == project_id
    assert item["repository_id"] is None
    assert item["repository_name"] is None
    assert item["git_url"] is None
    assert item["relative_path"] is None
    assert item["status"] == "ready"
    assert item["task_id"] == second["task_id"]
    assert item["task_status"] == "succeeded"
    assert "content" not in item and "content_preview" not in item and "user_id" not in item
    assert client.get(f"/api/v1/projects/{project_id}/sources?page=2&page_size=1").json()["items"][0]["id"] == first["source_id"]
    assert client.get(f"/api/v1/projects/{project_id}/sources?page=3&page_size=1").json()["items"] == []
    assert client.get(f"/api/v1/projects/{project_id}/sources?page=0").status_code == 422
    assert client.get(f"/api/v1/projects/{project_id}/sources?page_size=101").status_code == 422

    source = db_session.get(SourceDocument, uuid.UUID(first["source_id"]))
    latest = ProcessingTask(
        user_id=source.user_id, project_id=source.project_id, source_id=source.id,
        type="markdown_parsing", status=TaskStatus.FAILED, created_at=utc_now(),
    )
    db_session.add(latest)
    db_session.commit()
    data = client.get(f"/api/v1/projects/{project_id}/sources").json()
    first_item = next(item for item in data["items"] if item["id"] == first["source_id"])
    assert first_item["task_id"] == str(latest.id)
    assert first_item["task_status"] == "failed"


def test_source_list_project_and_user_boundaries(client: TestClient) -> None:
    first_project = create_project(client)
    second_project = create_project(client)
    result = upload(client, first_project, b"# Isolated")
    assert client.get(f"/api/v1/projects/{second_project}/sources").json()["total"] == 0
    assert client.get(f"/api/v1/projects/{uuid.uuid4()}/sources").status_code == 404
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(f"/api/v1/projects/{first_project}/sources").status_code == 404
        assert client.get(f"/api/v1/sources/{result['source_id']}").status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)


def test_source_without_task_is_listed(client: TestClient, db_session: Session) -> None:
    project_id = create_project(client)
    result = upload(client, project_id, b"# Kept")
    db_session.delete(db_session.get(ProcessingTask, uuid.UUID(result["task_id"])))
    db_session.commit()
    item = client.get(f"/api/v1/projects/{project_id}/sources").json()["items"][0]
    assert item["id"] == result["source_id"]
    assert item["task_id"] is None and item["task_status"] is None
