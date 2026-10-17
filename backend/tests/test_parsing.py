import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_id
from app.main import app
from app.models.domain import ProcessingTask, SourceChunk, SourceDocument, TaskStatus
from app.services import parsing
from tests.test_sources import create_project


def upload(client: TestClient, project_id: str, content: bytes = b"# Title\n\nA paragraph.\n\n- Evidence\n", name: str = "note.md") -> dict:
    response = client.post(f"/api/v1/projects/{project_id}/sources", files={"file": (name, content, "text/markdown")})
    assert response.status_code == 202
    return response.json()


def test_run_and_paginate_chunks_with_idempotent_reexecution(client: TestClient, db_session: Session) -> None:
    project_id = create_project(client)
    result = upload(client, project_id)
    chunks_url = f"/api/v1/sources/{result['source_id']}/chunks"
    assert client.get(chunks_url).json()["total"] == 0
    task_url = f"/api/v1/tasks/{result['task_id']}"
    task = client.post(f"{task_url}/run").json()
    assert task["status"] == "succeeded"
    assert task["type"] == "markdown_parsing"
    assert task["stage"] == "parsed"
    assert task["progress"] == 100
    assert task["error"] is None
    assert task["started_at"] and task["completed_at"]
    assert client.get(task_url).json() == task
    assert client.get(f"/api/v1/sources/{result['source_id']}").json()["status"] == "ready"
    chunks = client.get(chunks_url).json()
    assert chunks["total"] == 3
    assert [chunk["kind"] for chunk in chunks["items"]] == ["heading", "paragraph", "list"]
    assert chunks["items"][1]["heading_path"] == ["Title"]
    assert chunks["items"][1]["start_line"] == 3
    second_page = client.get(chunks_url, params={"page": 2, "page_size": 1}).json()
    assert second_page["items"] == [chunks["items"][1]]
    assert second_page["total"] == 3
    assert client.get(chunks_url, params={"page": 10}).json()["items"] == []
    assert client.get(chunks_url, params={"page_size": 101}).status_code == 422
    assert client.post(f"{task_url}/run").json() == task
    assert client.get(chunks_url).json() == chunks
    assert db_session.scalar(select(func.count()).select_from(SourceChunk)) == 3


def test_duplicate_upload_reuses_source_and_current_task_state(client: TestClient, db_session: Session) -> None:
    project_id = create_project(client)
    first = upload(client, project_id)
    assert upload(client, project_id, name="renamed.md") == first
    assert db_session.scalar(select(func.count()).select_from(SourceDocument)) == 1
    assert db_session.scalar(select(func.count()).select_from(ProcessingTask)) == 1
    client.post(f"/api/v1/tasks/{first['task_id']}/run")
    duplicate = upload(client, project_id)
    assert duplicate == {**first, "status": "succeeded"}
    assert upload(client, project_id, content=b"Changed")["source_id"] != first["source_id"]
    other_project = create_project(client)
    assert upload(client, other_project)["source_id"] != first["source_id"]


def test_parse_failure_rolls_back_partial_chunks_and_can_retry(client: TestClient, db_session: Session, monkeypatch) -> None:
    result = upload(client, create_project(client))
    task_url = f"/api/v1/tasks/{result['task_id']}/run"
    original = parsing.parse_markdown

    def fail(*args, **kwargs):
        raise ValueError("Private document text must not appear in response")

    monkeypatch.setattr(parsing, "parse_markdown", fail)
    failed = client.post(task_url)
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failed.json()["error"]["code"] == "SOURCE_PARSE_FAILED"
    assert "Private document" not in failed.text
    assert client.get(f"/api/v1/sources/{result['source_id']}").json()["status"] == "failed"
    assert db_session.scalar(select(func.count()).select_from(SourceChunk)) == 0
    monkeypatch.setattr(parsing, "parse_markdown", original)
    retried = client.post(task_url).json()
    assert retried["status"] == "succeeded"
    assert retried["error"] is None
    assert client.get(f"/api/v1/sources/{result['source_id']}").json()["status"] == "ready"


def test_chunk_write_failure_is_atomic(client: TestClient, db_session: Session, monkeypatch) -> None:
    result = upload(client, create_project(client))
    original = parsing.parse_markdown

    def duplicate_chunks(*args, **kwargs):
        chunks = original(*args, **kwargs)
        return [chunks[0], chunks[0]]

    monkeypatch.setattr(parsing, "parse_markdown", duplicate_chunks)
    response = client.post(f"/api/v1/tasks/{result['task_id']}/run")
    assert response.json()["status"] == "failed"
    assert db_session.scalar(select(func.count()).select_from(SourceChunk)) == 0


def test_running_and_cancelled_tasks_cannot_be_claimed(client: TestClient, db_session: Session) -> None:
    result = upload(client, create_project(client))
    task = db_session.get(ProcessingTask, uuid.UUID(result["task_id"]))
    for status in (TaskStatus.RUNNING, TaskStatus.CANCELLED):
        task.status = status
        db_session.commit()
        response = client.post(f"/api/v1/tasks/{task.id}/run")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "TASK_NOT_RUNNABLE"
        assert db_session.scalar(select(func.count()).select_from(SourceChunk)) == 0


def test_other_users_cannot_read_or_execute_sources(client: TestClient, db_session: Session) -> None:
    project_id = create_project(client)
    result = upload(client, project_id)
    client.post(f"/api/v1/tasks/{result['task_id']}/run")
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(f"/api/v1/sources/{result['source_id']}/chunks").status_code == 404
        assert client.post(f"/api/v1/tasks/{result['task_id']}/run").status_code == 404
        assert client.get(f"/api/v1/tasks/{result['task_id']}").status_code == 404
        assert client.post(f"/api/v1/projects/{project_id}/sources", files={"file": ("note.md", b"# Title", "text/markdown")}).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)


def test_missing_sources_and_tasks_return_not_found(client: TestClient) -> None:
    missing = uuid.uuid4()
    assert client.get(f"/api/v1/sources/{missing}/chunks").status_code == 404
    assert client.post(f"/api/v1/tasks/{missing}/run").status_code == 404


def test_legacy_queued_upload_can_be_parsed(client: TestClient, db_session: Session) -> None:
    result = upload(client, create_project(client))
    task = db_session.get(ProcessingTask, uuid.UUID(result["task_id"]))
    task.type = "knowledge_extraction"
    db_session.commit()
    assert client.post(f"/api/v1/tasks/{task.id}/run").json()["status"] == "succeeded"
