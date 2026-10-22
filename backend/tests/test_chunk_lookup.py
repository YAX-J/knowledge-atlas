import uuid

import pytest
from sqlalchemy import func, select

from app.api.dependencies import get_current_user_id
from app.main import app
from app.models.domain import ProcessingTask, Project, SourceChunk, SourceDocument, utc_now
from tests.test_parsing import upload
from tests.test_sources import create_project


def fixture_chunk(client, *, name="note.md", content=b"# Evidence\n\nExact original quote.\n"):
    project = create_project(client)
    source = upload(client, project, content=content, name=name)
    assert client.post(f"/api/v1/tasks/{source['task_id']}/run").json()["status"] == "succeeded"
    chunks = client.get(f"/api/v1/sources/{source['source_id']}/chunks", params={"page_size": 100}).json()["items"]
    chunk = chunks[-1]
    url = f"/api/v1/projects/{project}/sources/{source['source_id']}/chunks/{chunk['id']}"
    return project, source, chunk, url


@pytest.mark.parametrize("name,content", [("note.md", b"# Exact\r\n\r\nQuote with CRLF.\r\n"), ("Example.java", b"class Example {\n void run() {}\n}\n")])
def test_exact_chunk_lookup_reuses_original_bytes_position_and_uuid(client, db_session, name, content):
    _, _, chunk, url = fixture_chunk(client, name=name, content=content)
    before = db_session.scalar(select(func.count()).select_from(SourceChunk))
    response = client.get(url)
    assert response.status_code == 200, response.text
    assert response.json() == chunk
    assert db_session.scalar(select(func.count()).select_from(SourceChunk)) == before
    assert "user_id" not in response.json()


def test_lookup_locates_later_page_without_scanning_all_pages_or_requiring_task(client, db_session):
    _, source, chunk, url = fixture_chunk(client, content=("\n\n".join(f"Paragraph {i}." for i in range(65)) + "\n").encode())
    db_session.delete(db_session.get(ProcessingTask, uuid.UUID(source["task_id"])))
    db_session.commit()
    result = client.get(url).json()
    assert result["position"] == 64
    page = client.get(f"/api/v1/sources/{source['source_id']}/chunks", params={"page": result["position"] // 20 + 1}).json()
    assert chunk in page["items"] and page["page"] == 4


@pytest.mark.parametrize("boundary", ["user", "project", "source", "chunk", "archived", "source_user", "source_project", "chunk_user", "chunk_project"])
def test_chunk_lookup_checks_all_scope_and_archive_boundaries(client, db_session, boundary):
    project, source, chunk, url = fixture_chunk(client)
    if boundary == "user":
        app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    elif boundary == "project":
        url = url.replace(project, create_project(client))
    elif boundary == "source":
        other = upload(client, project, content=b"Other source.")
        url = url.replace(source["source_id"], other["source_id"])
    elif boundary == "chunk":
        url = url.replace(chunk["id"], str(uuid.uuid4()))
    elif boundary == "archived":
        db_session.get(Project, uuid.UUID(project)).archived_at = utc_now()
    elif boundary.startswith("source_"):
        setattr(db_session.get(SourceDocument, uuid.UUID(source["source_id"])), boundary.removeprefix("source_") + "_id", uuid.uuid4())
    else:
        setattr(db_session.get(SourceChunk, uuid.UUID(chunk["id"])), boundary.removeprefix("chunk_") + "_id", uuid.uuid4())
    db_session.commit()
    try:
        assert client.get(url).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


def test_unparsed_source_does_not_fabricate_a_chunk(client):
    project = create_project(client)
    source = upload(client, project)
    response = client.get(f"/api/v1/projects/{project}/sources/{source['source_id']}/chunks/{uuid.uuid4()}")
    assert response.status_code == 404 and response.json()["error"]["code"] == "SOURCE_CHUNK_NOT_FOUND"
