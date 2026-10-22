import uuid
from datetime import datetime, UTC, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_id
from app.api.routes import repositories as routes, knowledge as knowledge_routes
from app.core.config import Settings
from app.main import app
from app.models.domain import Project, RepositorySnapshot, SourceDocument, utc_now
from app.schemas.knowledge import ExtractionDraft
from app.services import deepseek
from app.services.source_links import github_line_url
from tests.test_github_import import create_project, register_github


def fixture_snapshot(client, db: Session, *, project=None, repository=None, sha="a" * 40, message="Use PostgreSQL for storage.", ref="main", timestamp=None):
    project = project or create_project(client)
    repository = repository or register_github(client, project)["id"]
    owner = db.get(Project, uuid.UUID(project))
    snapshot = RepositorySnapshot(
        user_id=owner.user_id, project_id=owner.id, repository_id=uuid.UUID(repository),
        provider="github", ref=ref, commit_sha=sha, tree_sha="b" * 40,
        commit_message=message, committed_at=timestamp,
    )
    db.add(snapshot)
    db.commit()
    url = f"/api/v1/projects/{project}/repositories/{repository}/snapshots/{snapshot.id}/commit-source"
    return project, repository, snapshot, url


def imported(client, url):
    response = client.post(url)
    assert response.status_code == 200, response.text
    return response.json()


def test_saved_commit_uses_normal_markdown_pipeline_and_current_task_status(client: TestClient, db_session: Session, monkeypatch):
    project, repository, snapshot, url = fixture_snapshot(client, db_session)
    # No provider/model request is needed to turn saved metadata into a source.
    monkeypatch.setattr(deepseek, "extract_candidates", lambda *args: pytest.fail("Unexpected model call"))
    result = imported(client, url)
    assert result["reused"] is False
    assert result["status"] == "queued"
    source = client.get(f"/api/v1/sources/{result['source_id']}").json()
    assert source["repository_id"] == repository
    assert source["source_type"] == "markdown"
    assert source["git_url"] == f"https://github.com/example/demo/commit/{'a' * 40}"
    assert "> Use PostgreSQL for storage." in source["content_preview"]
    assert "does not include a patch" in source["content_preview"]
    assert client.post(f"/api/v1/tasks/{result['task_id']}/run").json()["status"] == "succeeded"
    again = imported(client, url)
    assert again["reused"] and again["status"] == "succeeded"
    assert again["source_id"] == result["source_id"] and again["task_id"] == result["task_id"]
    assert db_session.scalar(select(func.count()).select_from(SourceDocument)) == 1
    history = client.get(f"/api/v1/projects/{project}/repositories/{repository}/snapshots").json()["items"][0]
    assert history["commit_source_id"] == result["source_id"]
    assert history["commit_task_id"] == result["task_id"]
    assert client.get(f"/api/v1/projects/{project}/graph").json()["nodes"] == []


def test_same_commit_refs_timezone_and_repository_rename_reuse_same_source(client, db_session):
    from app.models.domain import SourceRepository

    project, repository, _, url = fixture_snapshot(client, db_session, timestamp=datetime(2026, 10, 22, 1, tzinfo=UTC))
    first = imported(client, url)
    stored = db_session.get(SourceRepository, uuid.UUID(repository))
    stored.remote_name = "renamed"
    stored.remote_url = "https://github.com/example/renamed"
    db_session.commit()
    _, _, _, another = fixture_snapshot(client, db_session, project=project, repository=repository,
        ref="release", timestamp=datetime(2026, 10, 22, 9, tzinfo=timezone(timedelta(hours=8))))
    second = imported(client, another)
    assert second["reused"]
    assert second["source_id"] == first["source_id"]
    assert second["git_url"] == f"https://github.com/example/renamed/commit/{'a' * 40}"
    assert client.get(f"/api/v1/sources/{first['source_id']}").json()["git_url"] == second["git_url"]


def test_changed_commit_and_other_repository_do_not_deduplicate(client, db_session):
    project, repository, _, url = fixture_snapshot(client, db_session)
    first = imported(client, url)
    _, _, _, another = fixture_snapshot(client, db_session, project=project, repository=repository, sha="c" * 40)
    second = imported(client, another)
    other = client.post(f"/api/v1/projects/{project}/repositories/resolve-github", json={"remote_url": "https://github.com/example/other"}).json()["id"]
    _, _, _, third_url = fixture_snapshot(client, db_session, project=project, repository=other)
    third = imported(client, third_url)
    assert len({item["source_id"] for item in (first, second, third)}) == 3


@pytest.mark.parametrize("broken", ["missing_task", "foreign_source"])
def test_incompatible_mapping_is_repaired_without_reusing_foreign_source(client, db_session, broken):
    _, _, snapshot, url = fixture_snapshot(client, db_session)
    first = imported(client, url)
    if broken == "missing_task":
        snapshot.commit_task_id = None
    else:
        _, _, _, other_url = fixture_snapshot(client, db_session)
        foreign = imported(client, other_url)
        snapshot.commit_source_id = uuid.UUID(foreign["source_id"])
        snapshot.commit_task_id = uuid.UUID(foreign["task_id"])
    db_session.commit()
    repaired = imported(client, url)
    assert repaired["reused"]
    assert repaired["source_id"] == first["source_id"]
    assert repaired["task_id"] == first["task_id"]
    db_session.refresh(snapshot)
    assert str(snapshot.commit_source_id) == first["source_id"]


@pytest.mark.parametrize("message", ["", "# Heading\n\n```java\nignored\n```\n<script>alert(1)</script>", "中文提交说明\r\n第二行"])
def test_empty_multiline_and_untrusted_messages_remain_plain_source_text(client, db_session, message):
    _, _, _, url = fixture_snapshot(client, db_session, message=message)
    result = imported(client, url)
    assert client.post(f"/api/v1/tasks/{result['task_id']}/run").json()["status"] == "succeeded"
    content = db_session.get(SourceDocument, uuid.UUID(result["source_id"])).content
    for line in message.splitlines():
        assert f"> {line}" in content
    if not message:
        assert "(No commit message saved)" in content


def test_size_limit_rejects_without_mapping_or_partial_source(client, db_session, monkeypatch):
    _, _, snapshot, url = fixture_snapshot(client, db_session, message="x" * 1000)
    monkeypatch.setattr(routes, "get_settings", lambda: Settings(_env_file=None, max_upload_bytes=200))
    response = client.post(url)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "SOURCE_TOO_LARGE"
    db_session.refresh(snapshot)
    assert snapshot.commit_source_id is None
    assert db_session.scalar(select(func.count()).select_from(SourceDocument)) == 0


@pytest.mark.parametrize("boundary", ["project", "repository", "user", "archived", "snapshot"])
def test_import_checks_all_scope_boundaries(client, db_session, boundary):
    project, repository, _, url = fixture_snapshot(client, db_session)
    if boundary == "project":
        url = url.replace(project, create_project(client))
    elif boundary == "repository":
        other = client.post(f"/api/v1/projects/{project}/repositories/resolve", json={"name": "other"}).json()["id"]
        url = url.replace(repository, other)
    elif boundary == "user":
        app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    elif boundary == "archived":
        db_session.get(Project, uuid.UUID(project)).archived_at = utc_now()
        db_session.commit()
    else:
        url = url.replace(url.split('/')[-2], str(uuid.uuid4()))
    try:
        assert client.post(url).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert db_session.scalar(select(func.count()).select_from(SourceDocument)) == 0


def test_invalid_sha_is_not_used_as_filename(client, db_session):
    _, _, _, url = fixture_snapshot(client, db_session, sha="../bad")
    assert client.post(url).json()["error"]["code"] == "SNAPSHOT_COMMIT_INVALID"


def test_commit_evidence_can_be_reviewed_and_keeps_canonical_commit_url(client, db_session, monkeypatch):
    project, _, _, url = fixture_snapshot(client, db_session)
    source = imported(client, url)
    client.post(f"/api/v1/tasks/{source['task_id']}/run")
    chunks = client.get(f"/api/v1/sources/{source['source_id']}/chunks").json()["items"]
    chunk = next(item for item in chunks if "Use PostgreSQL" in item["content"])
    draft = ExtractionDraft.model_validate({"entities": [{
        "local_id": "decision", "type": "Decision", "name": "Commit storage decision",
        "summary": "Use PostgreSQL", "confidence": .9,
        "evidence": [{"chunk_id": chunk["id"], "quote": "Use PostgreSQL for storage."}],
    }], "relations": []})
    monkeypatch.setattr(knowledge_routes, "get_settings", lambda: Settings(_env_file=None, deepseek_api_key="fixture-key"))
    monkeypatch.setattr(deepseek, "extract_candidates", lambda *args: draft)
    assert client.post(f"/api/v1/sources/{source['source_id']}/extract").status_code == 200
    candidate = client.get(f"/api/v1/projects/{project}/reviews").json()["items"][0]
    confirmed = client.post(f"/api/v1/reviews/{candidate['id']}/resolve", json={"action": "confirm"}).json()
    evidence = client.get(f"/api/v1/knowledge/entities/{confirmed['knowledge_id']}").json()["evidence"][0]
    assert evidence["source_id"] == source["source_id"]
    assert evidence["git_url"] == source["git_url"]
    assert "#L" not in evidence["git_url"]
    assert github_line_url(source["git_url"], start_line=1, end_line=5) == source["git_url"]
