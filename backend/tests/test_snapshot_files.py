import uuid

import pytest
from sqlalchemy import func, select

from app.api.dependencies import get_current_user_id
from app.main import app
from app.models.domain import ProcessingTask, Project, RepositorySnapshotFile, SourceDocument, SourceRepository, utc_now
from tests.test_commit_sources import fixture_snapshot


def fixture_file(client, db, *, path="docs/设计 #1.md", status="imported", **kwargs):
    project, repository, snapshot, _ = fixture_snapshot(client, db, **kwargs)
    response = client.post(f"/api/v1/projects/{project}/sources", data={
        "repository_id": repository, "relative_path": "docs/note.md",
    }, files={"file": ("note.md", b"# Original\n\nImmutable evidence.", "text/markdown")})
    assert response.status_code == 202, response.text
    source = response.json()
    record = RepositorySnapshotFile(snapshot_id=snapshot.id, path=path, blob_sha="d"*40,
        size_bytes=31, source_id=uuid.UUID(source["source_id"]), task_id=uuid.UUID(source["task_id"]), status=status)
    db.add(record)
    db.commit()
    url = f"/api/v1/projects/{project}/repositories/{repository}/snapshots/{snapshot.id}/files"
    return project, repository, snapshot, record, source, url


@pytest.mark.parametrize("status", ["imported", "reused", "unchanged", "renamed", "deleted", "skipped"])
def test_snapshot_file_states_keep_exact_snapshot_links_and_safe_source_mapping(client, db_session, status):
    _, repository, snapshot, record, source, url = fixture_file(client, db_session, status=status)
    record.previous_path = "old.md" if status == "renamed" else None
    record.error_code = "SOURCE_TOO_LARGE" if status == "skipped" else None
    snapshot.truncated, snapshot.deletion_detection_complete = True, False
    db_session.commit()
    before_sources = db_session.scalar(select(func.count()).select_from(SourceDocument))
    before_tasks = db_session.scalar(select(func.count()).select_from(ProcessingTask))
    result = client.get(url)
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["snapshot_id"] == str(snapshot.id) and payload["repository_id"] == repository
    assert payload["truncated"] and not payload["deletion_detection_complete"]
    item = payload["items"][0]
    assert item["status"] == status and item["previous_path"] == record.previous_path
    assert item["error_code"] == record.error_code and item["blob_sha"] == "d" * 40
    assert item["source_id"] == (None if status == "skipped" else source["source_id"])
    assert item["task_id"] == (None if status == "skipped" else source["task_id"])
    assert item["git_url"] == (None if status == "deleted" else f"https://github.com/example/demo/blob/{snapshot.commit_sha}/docs/%E8%AE%BE%E8%AE%A1%20%231.md")
    assert "content" not in item and "result" not in item
    assert db_session.scalar(select(func.count()).select_from(SourceDocument)) == before_sources
    assert db_session.scalar(select(func.count()).select_from(ProcessingTask)) == before_tasks


def test_file_pagination_is_path_stable_and_total_includes_deleted_rows(client, db_session):
    _, _, snapshot, record, _, url = fixture_file(client, db_session, path="c.md")
    for path in ["b.md", "a.md"]:
        db_session.add(RepositorySnapshotFile(snapshot_id=snapshot.id, path=path, blob_sha="e"*40,
                                             size_bytes=1, status="deleted"))
    db_session.commit()
    first = client.get(url, params={"page_size": 2}).json()
    second = client.get(url, params={"page_size": 2, "page": 2}).json()
    assert first["total"] == 3 and [item["path"] for item in first["items"]] == ["a.md", "b.md"]
    assert second["items"][0]["id"] == str(record.id)
    assert client.get(url, params={"page": 3, "page_size": 2}).json()["items"] == []


@pytest.mark.parametrize("broken", ["foreign_project", "foreign_repository", "foreign_user", "wrong_task_source", "wrong_task_type", "wrong_source_type", "missing_source", "missing_task"])
def test_missing_or_incompatible_links_never_expose_foreign_source_or_task(client, db_session, broken):
    project, repository, _, record, source, url = fixture_file(client, db_session)
    stored_source = db_session.get(SourceDocument, record.source_id)
    task = db_session.get(ProcessingTask, record.task_id)
    if broken == "foreign_project":
        stored_source.project_id = uuid.uuid4()
    elif broken == "foreign_repository":
        stored_source.repository_id = uuid.uuid4()
    elif broken == "foreign_user":
        stored_source.user_id = uuid.uuid4()
    elif broken == "wrong_task_source":
        task.source_id = uuid.uuid4()
    elif broken == "wrong_task_type":
        task.type = "code_parsing"
    elif broken == "wrong_source_type":
        stored_source.source_type = "java"
    elif broken == "missing_source":
        record.source_id = None
    else:
        record.task_id = None
    db_session.commit()
    item = client.get(url).json()["items"][0]
    source_allowed = broken in {"wrong_task_source", "wrong_task_type", "missing_task"}
    assert item["source_id"] == (source["source_id"] if source_allowed else None)
    assert item["task_id"] is None
    assert item["source_status"] == ("uploaded" if source_allowed else None)


@pytest.mark.parametrize("boundary", ["project", "repository", "user", "archived", "snapshot"])
def test_snapshot_file_history_is_scoped_and_archived_projects_are_hidden(client, db_session, boundary):
    project, repository, snapshot, _, _, url = fixture_file(client, db_session)
    if boundary == "project":
        url = url.replace(project, str(uuid.uuid4()))
    elif boundary == "repository":
        url = url.replace(repository, str(uuid.uuid4()))
    elif boundary == "user":
        app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    elif boundary == "archived":
        db_session.get(Project, uuid.UUID(project)).archived_at = utc_now()
        db_session.commit()
    else:
        url = url.replace(str(snapshot.id), str(uuid.uuid4()))
    try:
        assert client.get(url).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)


def test_links_stay_on_selected_commit_after_later_sync_and_repository_rename(client, db_session):
    _, repository, snapshot, _, _, url = fixture_file(client, db_session, path="README.md")
    remote = db_session.get(SourceRepository, uuid.UUID(repository))
    remote.remote_name, remote.remote_url = "renamed", "https://github.com/example/renamed"
    db_session.commit()
    result = client.get(url).json()["items"][0]
    assert result["git_url"] == f"https://github.com/example/renamed/blob/{snapshot.commit_sha}/README.md"


@pytest.mark.parametrize("page,page_size", [(0, 20), (1, 0), (1, 101)])
def test_snapshot_file_pagination_bounds(client, db_session, page, page_size):
    *_, url = fixture_file(client, db_session)
    assert client.get(url, params={"page": page, "page_size": page_size}).status_code == 422


def test_empty_snapshot_and_invalid_path_do_not_invent_files_or_links(client, db_session):
    _, _, _, record, _, url = fixture_file(client, db_session, path="../bad.md")
    assert client.get(url).json()["items"][0]["git_url"] is None
    db_session.delete(record)
    db_session.commit()
    result = client.get(url).json()
    assert result["items"] == [] and result["total"] == 0
