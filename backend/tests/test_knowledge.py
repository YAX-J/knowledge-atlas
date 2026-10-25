import copy
import uuid
from datetime import timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_id
from app.api.routes import knowledge as routes
from app.core.config import Settings
from app.main import app
from app.models.domain import (
    CandidateKnowledge, ProcessingTask, Project, ReviewEvent, ReviewStatus, SourceDocument,
    TaskStatus, utc_now,
)
from app.schemas.knowledge import ExtractionDraft
from app.services import deepseek, knowledge
from tests.test_parsing import upload
from tests.test_sources import create_project


@pytest.fixture
def configured(monkeypatch):
    settings = Settings(_env_file=None, deepseek_api_key=SecretStr("test-secret-key"))
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    return settings


def parsed_source(client: TestClient) -> tuple[str, dict, dict]:
    project_id = create_project(client)
    source = upload(client, project_id, content="# Decision\n\nUse PostgreSQL for storage.\n".encode())
    assert client.post(f"/api/v1/tasks/{source['task_id']}/run").json()["status"] == "succeeded"
    chunk = client.get(f"/api/v1/sources/{source['source_id']}/chunks").json()["items"][1]
    evidence = [{"chunk_id": chunk["id"], "quote": "Use PostgreSQL for storage."}]
    draft = {
        "entities": [
            {"local_id": "decision", "type": "Decision", "name": "Store knowledge", "summary": "Use PostgreSQL", "confidence": .9, "evidence": evidence},
            {"local_id": "postgres", "type": "Technology", "name": "PostgreSQL", "summary": "Storage database", "confidence": .9, "evidence": evidence},
        ],
        "relations": [{"local_id": "uses", "type": "USES", "source": "decision", "target": "postgres", "summary": "Decision uses PostgreSQL", "confidence": .9, "evidence": evidence}],
    }
    return project_id, source, draft


def reviews(client, project_id, **params):
    response = client.get(f"/api/v1/projects/{project_id}/reviews", params=params)
    assert response.status_code == 200
    return response.json()


def test_lease_expiry_respects_postgresql_session_timezone():
    now = utc_now()
    local_timezone = timezone(timedelta(hours=8))
    assert not knowledge.lease_is_active((now - timedelta(seconds=1)).astimezone(local_timezone), now)
    assert knowledge.lease_is_active((now + timedelta(seconds=1)).astimezone(local_timezone), now)
    assert not knowledge.lease_is_active((now - timedelta(seconds=1)).replace(tzinfo=None), now)


def test_extract_and_review_with_evidence_and_idempotency(client: TestClient, db_session: Session, configured, monkeypatch):
    project_id, source, draft = parsed_source(client)
    calls = []
    def extract(settings, chunks):
        calls.append(chunks)
        return ExtractionDraft.model_validate(draft)
    monkeypatch.setattr(deepseek, "extract_candidates", extract)
    url = f"/api/v1/sources/{source['source_id']}/extract"
    assert client.get(url.replace('/extract', '/extraction')).json() == {"task": None, "candidate_count": 0, "review_counts": {"pending": 0, "confirmed": 0, "rejected": 0}}
    response = client.post(url)
    assert response.status_code == 200
    result = response.json()
    assert result["candidate_count"] == 3
    assert result["task"]["type"] == "knowledge_candidates"
    assert result["task"]["status"] == "succeeded"
    replay = client.post(url).json()
    assert replay['task'] == result['task'] and replay['candidate_count'] == result['candidate_count']
    assert replay['review_counts'] == {'pending': 3, 'confirmed': 0, 'rejected': 0}
    assert len(calls) == 1
    assert client.get(f"/api/v1/sources/{source['source_id']}").json()["status"] == "ready"
    listing = reviews(client, project_id)
    assert listing["total"] == 3
    assert all(item["review_status"] == "pending" for item in listing["items"])
    assert listing["items"][0]["evidence"][0]["start_line"] == 3
    assert len(reviews(client, project_id, page_size=1)["items"]) == 1
    assert reviews(client, project_id, page=20)["items"] == []
    assert reviews(client, project_id, candidate_type="Technology")["total"] == 1
    assert reviews(client, project_id, min_confidence=.95)["total"] == 0
    items = listing["items"]
    relationship = next(item for item in items if item["kind"] == "relation")
    resolve_url = f"/api/v1/reviews/{relationship['id']}/resolve"
    assert client.post(resolve_url, json={"action": "confirm"}).status_code == 409
    for item in items:
        if item["kind"] == "entity":
            decision = {"action": "confirm", "changes": {"name": item["name"] + " reviewed"}}
            endpoint = f"/api/v1/reviews/{item['id']}/resolve"
            resolved = client.post(endpoint, json=decision)
            assert resolved.status_code == 200
            assert resolved.json()["review_status"] == "confirmed"
            assert client.post(endpoint, json=decision).json() == resolved.json()
            assert client.post(endpoint, json={"action": "reject"}).status_code == 409
    assert client.post(resolve_url, json={"action": "confirm"}).status_code == 200
    assert db_session.scalar(select(func.count()).select_from(ReviewEvent)) == 3
    event = db_session.scalar(select(ReviewEvent).where(ReviewEvent.candidate_id == uuid.UUID(items[0]["id"])))
    assert event.before["review_status"] == "pending" and event.after["review_status"] == "confirmed"
    assert reviews(client, project_id, review_status="pending")["total"] == 0
    replay = client.post(url).json()
    assert replay['task'] == result['task'] and replay['candidate_count'] == result['candidate_count']
    assert replay['review_counts'] == {'pending': 0, 'confirmed': 3, 'rejected': 0}
    assert len(calls) == 1
    # Upload and source-list task references must remain parsing tasks.
    assert upload(client, project_id, content=b"# Decision\n\nUse PostgreSQL for storage.\n")["task_id"] == source["task_id"]
    assert client.get(f"/api/v1/projects/{project_id}/sources").json()["items"][0]["task_id"] == source["task_id"]


@pytest.mark.parametrize("problem", ["quote", "chunk"])
def test_invalid_evidence_rejects_entire_batch_and_retry_is_safe(client, db_session, configured, monkeypatch, problem):
    project_id, source, draft = parsed_source(client)
    valid = copy.deepcopy(draft)
    draft["relations"][0]["evidence"] = [{
        "chunk_id": str(uuid.uuid4()) if problem == "chunk" else draft["entities"][0]["evidence"][0]["chunk_id"],
        "quote": "Use PostgreSQL for storage." if problem == "chunk" else "Invented secret model output",
    }]
    monkeypatch.setattr(deepseek, "extract_candidates", lambda *_: ExtractionDraft.model_validate(draft))
    url = f"/api/v1/sources/{source['source_id']}/extract"
    failed = client.post(url)
    assert failed.json()["task"]["error"]["code"] == "EXTRACTION_EVIDENCE_INVALID"
    assert "Invented secret" not in failed.text
    assert failed.json()["task"]["status"] == "failed"
    assert reviews(client, project_id)["total"] == 0
    assert db_session.scalar(select(func.count()).select_from(CandidateKnowledge)) == 0
    assert client.get(f"/api/v1/sources/{source['source_id']}").json()["status"] == "ready"
    monkeypatch.setattr(deepseek, "extract_candidates", lambda *_: ExtractionDraft.model_validate(valid))
    assert client.post(url).json()["candidate_count"] == 3


def test_configuration_parse_and_size_preconditions(client, configured, monkeypatch):
    project_id = create_project(client)
    source = upload(client, project_id)
    url = f"/api/v1/sources/{source['source_id']}/extract"
    assert client.post(url).json()["error"]["code"] == "SOURCE_NOT_PARSED"
    client.post(f"/api/v1/tasks/{source['task_id']}/run")
    configured.deepseek_api_key = None
    assert client.post(url).json()["error"]["code"] == "EXTRACTION_NOT_CONFIGURED"
    assert client.get(url.replace('/extract', '/extraction')).json()["task"] is None
    configured.deepseek_api_key = SecretStr("test")
    configured.extraction_max_input_chars = 1
    assert client.post(url).status_code == 413


def test_active_lease_and_stale_success_are_fenced(client, db_session, configured, monkeypatch):
    project_id, source, draft = parsed_source(client)
    def replace_run(*_):
        task = db_session.get(ProcessingTask, knowledge.extraction_task_id(uuid.UUID(source["source_id"])))
        assert client.post(f"/api/v1/sources/{source['source_id']}/extract").status_code == 409
        task.execution_id = uuid.uuid4()
        task.lease_expires_at = utc_now() + timedelta(seconds=300)
        db_session.commit()
        return ExtractionDraft.model_validate(draft)
    monkeypatch.setattr(deepseek, "extract_candidates", replace_run)
    response = client.post(f"/api/v1/sources/{source['source_id']}/extract")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EXTRACTION_REPLACED"
    assert reviews(client, project_id)["total"] == 0
    task = db_session.get(ProcessingTask, knowledge.extraction_task_id(uuid.UUID(source["source_id"])))
    task.lease_expires_at = utc_now() - timedelta(seconds=1)
    db_session.commit()
    monkeypatch.setattr(deepseek, "extract_candidates", lambda *_: ExtractionDraft.model_validate(draft))
    assert client.post(f"/api/v1/sources/{source['source_id']}/extract").json()["candidate_count"] == 3
    assert task.attempt_count == 2


def test_rejection_boundaries_and_archived_projects(client, db_session, configured, monkeypatch):
    project_id, source, draft = parsed_source(client)
    monkeypatch.setattr(deepseek, "extract_candidates", lambda *_: ExtractionDraft.model_validate(draft))
    client.post(f"/api/v1/sources/{source['source_id']}/extract")
    items = reviews(client, project_id)["items"]
    entity = next(item for item in items if item["kind"] == "entity")
    relationship = next(item for item in items if item["kind"] == "relation")
    endpoint = f"/api/v1/reviews/{entity['id']}/resolve"
    assert client.post(endpoint, json={"action": "reject", "changes": {"name": "Wrong"}}).status_code == 422
    assert client.post(endpoint, json={"action": "merge"}).status_code == 422
    assert client.post(endpoint, json={"action": "reject"}).json()["review_status"] == "rejected"
    assert client.post(endpoint, json={"action": "reject"}).status_code == 200
    assert client.post(f"/api/v1/reviews/{relationship['id']}/resolve", json={"action": "confirm"}).status_code == 409
    other = create_project(client)
    assert reviews(client, other)["total"] == 0
    assert client.get(f"/api/v1/projects/{other}/reviews", params={"source_id": source["source_id"]}).status_code == 404
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(f"/api/v1/projects/{project_id}/reviews").status_code == 404
        assert client.get(f"/api/v1/sources/{source['source_id']}/extraction").status_code == 404
        assert client.post(f"/api/v1/sources/{source['source_id']}/extract").status_code == 404
        assert client.post(endpoint, json={"action": "reject"}).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)
    project = db_session.get(Project, uuid.UUID(project_id))
    project.archived_at = utc_now()
    db_session.commit()
    assert client.get(f"/api/v1/projects/{project_id}/reviews").status_code == 404
    assert client.post(endpoint, json={"action": "reject"}).status_code == 404


@pytest.mark.parametrize("mutation", ["unknown_type", "unknown_endpoint", "duplicate_id", "confidence", "missing_evidence", "extra_field"])
def test_draft_contract_rejects_invalid_model_output(mutation):
    evidence = [{"chunk_id": str(uuid.uuid4()), "quote": "Evidence"}]
    value = {"entities": [{"local_id": "a", "type": "Concept", "name": "A", "summary": "Summary", "confidence": .8, "evidence": evidence}], "relations": []}
    if mutation == "unknown_type": value["entities"][0]["type"] = "InventedType"
    if mutation == "unknown_endpoint": value["relations"] = [{"local_id": "b", "type": "USES", "source": "a", "target": "missing", "summary": "Uses", "confidence": .8, "evidence": evidence}]
    if mutation == "duplicate_id": value["entities"] *= 2
    if mutation == "confidence": value["entities"][0]["confidence"] = float('nan')
    if mutation == "missing_evidence": value["entities"][0]["evidence"] = []
    if mutation == "extra_field": value["entities"][0]["review_status"] = "confirmed"
    with pytest.raises(ValueError):
        ExtractionDraft.model_validate(value)


@pytest.mark.parametrize("mode", ["success", "401", "429", "bad_json", "length", "timeout", "oversized"])
def test_deepseek_transport_is_bounded_and_sanitized(monkeypatch, configured, mode):
    captured = []
    def respond(request):
        captured.append(request)
        if mode == "timeout": raise httpx.ReadTimeout("test-secret-key private input", request=request)
        if mode in {"401", "429"}: return httpx.Response(int(mode), text="test-secret-key private input")
        if mode == "oversized": return httpx.Response(200, content=b"x" * (1024 * 1024 + 1))
        return httpx.Response(200, json={"choices": [{"finish_reason": "length" if mode == "length" else "stop", "message": {"content": "private invalid output" if mode == "bad_json" else '{"entities": [], "relations": []}'}}]})
    original = httpx.Client
    monkeypatch.setattr(deepseek.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    if mode == "success":
        assert deepseek.extract_candidates(configured, []).entities == []
    else:
        with pytest.raises(deepseek.ExtractionError) as error:
            deepseek.extract_candidates(configured, [])
        assert "test-secret-key" not in str(error.value) and "private" not in str(error.value)
    import json
    body = json.loads(captured[0].content)
    assert body["response_format"] == {"type": "json_object"}
    assert body["thinking"] == {"type": "disabled"}
    assert captured[0].url == "https://api.deepseek.com/chat/completions"
