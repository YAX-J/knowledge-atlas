import copy
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.api.dependencies import get_current_user_id
from app.main import app
from app.models.domain import Project, SourceChunk, utc_now
from app.models.evolution import KnowledgeChange
from app.models.graph import KnowledgeEntity, KnowledgeEvidence
from app.schemas.knowledge import ExtractionDraft
from app.services import deepseek, evolution
from tests.test_graph import confirm, extracted
from tests.test_knowledge import configured, reviews
from tests.test_parsing import upload
from tests.test_sources import create_project


def reviewed_decision(client, monkeypatch, project, version, *, name="Storage decision", summary=None):
    text = f"Use storage version {version}."
    source = upload(client, project, content=f"# Decision {version}\n\n{text}\n".encode())
    assert client.post(f"/api/v1/tasks/{source['task_id']}/run").json()["status"] == "succeeded"
    chunk = client.get(f"/api/v1/sources/{source['source_id']}/chunks").json()["items"][1]
    draft = {"entities": [{"local_id": "decision", "type": "Decision", "name": name,
                           "summary": summary or text, "confidence": .9,
                           "evidence": [{"chunk_id": chunk["id"], "quote": text}]}], "relations": []}
    monkeypatch.setattr(deepseek, "extract_candidates", lambda *_: ExtractionDraft.model_validate(draft))
    assert client.post(f"/api/v1/sources/{source['source_id']}/extract").json()["candidate_count"] == 1
    candidate = reviews(client, project, source_id=source["source_id"])["items"][0]
    entity_id = confirm(client, candidate)["knowledge_id"]
    return client.get(f"/api/v1/knowledge/entities/{entity_id}").json()


def pair(client, monkeypatch):
    project = create_project(client)
    old = reviewed_decision(client, monkeypatch, project, 1)
    new = reviewed_decision(client, monkeypatch, project, 2)
    return project, old, new


def proposal(old, new, **changes):
    return {"old_entity_id": old["entity"]["id"], "new_entity_id": new["entity"]["id"],
            "evidence_id": new["evidence"][0]["id"], "kind": "SUPERSEDES",
            "reason": "Reviewed replacement based on source evidence.", "effective_at": utc_now().isoformat(), **changes}


def propose(client, project, data):
    response = client.post(f"/api/v1/projects/{project}/knowledge-changes", json=data)
    assert response.status_code == 200, response.text
    return response.json()


def resolve(client, project, change, action="confirm"):
    return client.post(f"/api/v1/projects/{project}/knowledge-changes/{change['id']}/resolve", json={"action": action})


def test_replacement_is_reviewed_atomic_idempotent_and_time_filtered(client, db_session, configured, monkeypatch):
    project, old, new = pair(client, monkeypatch)
    data = proposal(old, new)
    change = propose(client, project, data)
    assert change["review_status"] == "pending" and not change["before"] and not change["after"]
    assert propose(client, project, data) == change
    graph_url = f"/api/v1/projects/{project}/graph"
    assert len(client.get(graph_url).json()["nodes"]) == 2  # proposal is not a formal change
    resolved = resolve(client, project, change)
    assert resolved.status_code == 200, resolved.text
    result = resolved.json()
    assert result["review_status"] == "confirmed" and result["resolved_at"]
    assert result["before"]["old"]["status"] == "active"
    assert result["after"]["old"]["status"] == "superseded"
    assert result["after"]["old"]["valid_to"] == result["after"]["new"]["valid_from"]
    assert resolve(client, project, change).json() == result
    assert resolve(client, project, change, "reject").status_code == 409
    assert propose(client, project, data) == result
    assert db_session.scalar(select(func.count()).select_from(KnowledgeChange)) == 1
    assert [item["id"] for item in client.get(graph_url).json()["nodes"]] == [new["entity"]["id"]]
    assert client.get(f"/api/v1/knowledge/entities/{old['entity']['id']}").status_code == 404
    cutover = evolution.aware(db_session.get(KnowledgeChange, uuid.UUID(change["id"])).effective_at)
    historical = {"valid_at": (cutover - timedelta(microseconds=1)).isoformat()}
    assert [item["id"] for item in client.get(graph_url, params=historical).json()["nodes"]] == [old["entity"]["id"]]
    assert client.get(f"/api/v1/knowledge/entities/{old['entity']['id']}", params=historical).status_code == 200
    assert client.get(f"/api/v1/knowledge/entities/{new['entity']['id']}", params=historical).status_code == 404
    search_url = f"/api/v1/projects/{project}/search"
    assert [item["entity"]["id"] for item in client.get(search_url, params={"q": "Storage"}).json()["items"]] == [new["entity"]["id"]]
    assert [item["entity"]["id"] for item in client.get(search_url, params={"q": "Storage", **historical}).json()["items"]] == [old["entity"]["id"]]
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEvidence)) == 2


def test_three_versions_have_a_complete_new_to_old_chain_and_evidence(client, configured, monkeypatch):
    project, first, second = pair(client, monkeypatch)
    c1 = propose(client, project, proposal(first, second))
    assert resolve(client, project, c1).status_code == 200
    third = reviewed_decision(client, monkeypatch, project, 3)
    c2 = propose(client, project, proposal(second, third))
    assert resolve(client, project, c2).status_code == 200
    for entity in (first, second, third):
        response = client.get(f"/api/v1/projects/{project}/knowledge/entities/{entity['entity']['id']}/history")
        assert response.status_code == 200
        result = response.json()
        assert not result["truncated"]
        assert [item["id"] for item in result["entities"]] == [item["entity"]["id"] for item in (first, second, third)]
        assert [(item["new_entity_id"], item["old_entity_id"]) for item in result["changes"]] == [
            (second["entity"]["id"], first["entity"]["id"]), (third["entity"]["id"], second["entity"]["id"])]
        assert all(item["evidence"][0]["quote"].startswith("Use storage version") for item in result["changes"])
        assert "user_id" not in str(result)


@pytest.mark.parametrize("kind", ["SUPPLEMENTS", "CONFLICTS_WITH"])
def test_supplement_and_conflict_are_audited_without_rewriting_intervals(client, configured, monkeypatch, kind):
    project, old, new = pair(client, monkeypatch)
    change = propose(client, project, proposal(old, new, kind=kind))
    result = resolve(client, project, change).json()
    assert result["before"] == result["after"] and result["kind"] == kind
    assert len(client.get(f"/api/v1/projects/{project}/graph").json()["nodes"]) == 2


def test_rejection_is_idempotent_and_does_not_change_knowledge(client, configured, monkeypatch):
    project, old, new = pair(client, monkeypatch)
    change = propose(client, project, proposal(old, new))
    rejected = resolve(client, project, change, "reject").json()
    assert rejected["review_status"] == "rejected" and rejected["before"] == rejected["after"]
    assert resolve(client, project, change, "reject").json() == rejected
    assert resolve(client, project, change).status_code == 409
    assert len(client.get(f"/api/v1/projects/{project}/graph").json()["nodes"]) == 2


@pytest.mark.parametrize("problem", ["same", "type", "foreign_entity", "foreign_evidence", "quote", "early", "future", "inactive"])
def test_invalid_proposals_do_not_mutate_or_persist(client, db_session, configured, monkeypatch, problem):
    project, old, new = pair(client, monkeypatch)
    data = proposal(old, new)
    entity = db_session.get(KnowledgeEntity, uuid.UUID(new["entity"]["id"]))
    if problem == "same": data["old_entity_id"] = data["new_entity_id"]
    if problem == "type": entity.type = "Technology"
    if problem == "foreign_entity": data["old_entity_id"] = str(uuid.uuid4())
    if problem == "foreign_evidence": data["evidence_id"] = str(uuid.uuid4())
    if problem == "quote": db_session.get(KnowledgeEvidence, uuid.UUID(data["evidence_id"])).quote = "fabricated"
    if problem == "early": data["effective_at"] = (utc_now() - timedelta(days=1)).isoformat()
    if problem == "future": data["effective_at"] = (utc_now() + timedelta(days=1)).isoformat()
    if problem == "inactive": entity.status = "archived"
    db_session.commit()
    response = client.post(f"/api/v1/projects/{project}/knowledge-changes", json=data)
    assert response.status_code in {404, 409}, response.text
    assert db_session.scalar(select(func.count()).select_from(KnowledgeChange)) == 0
    assert db_session.get(KnowledgeEntity, uuid.UUID(old["entity"]["id"])).valid_to is None


def test_stale_confirmation_revalidates_and_rolls_back(client, db_session, configured, monkeypatch):
    project, old, new = pair(client, monkeypatch)
    third = reviewed_decision(client, monkeypatch, project, 3)
    stale = propose(client, project, proposal(old, new))
    winner = propose(client, project, proposal(old, third))
    assert resolve(client, project, winner).status_code == 200
    assert resolve(client, project, stale).status_code == 409
    row = db_session.get(KnowledgeChange, uuid.UUID(stale["id"]))
    assert row.review_status == "pending" and row.resolved_at is None and not row.before
    assert resolve(client, project, stale, "reject").status_code == 200


def test_cannot_fork_or_cycle_a_confirmed_replacement(client, configured, monkeypatch):
    project, old, new = pair(client, monkeypatch)
    third = reviewed_decision(client, monkeypatch, project, 3)
    change = propose(client, project, proposal(old, new))
    assert resolve(client, project, change).status_code == 200
    for data in (proposal(third, new), proposal(new, old)):
        assert client.post(f"/api/v1/projects/{project}/knowledge-changes", json=data).status_code == 409


def test_project_user_archived_scope_and_pagination(client, db_session, configured, monkeypatch):
    project, old, new = pair(client, monkeypatch)
    change = propose(client, project, proposal(old, new))
    other = create_project(client)
    for method, path, body in [
        ("post", f"/projects/{other}/knowledge-changes", proposal(old, new)),
        ("post", f"/projects/{other}/knowledge-changes/{change['id']}/resolve", {"action": "confirm"}),
        ("get", f"/projects/{other}/knowledge/entities/{old['entity']['id']}/history", None),
    ]:
        response = getattr(client, method)("/api/v1" + path, **({"json": body} if body else {}))
        assert response.status_code == 404
    url = f"/api/v1/projects/{project}/knowledge-changes"
    assert client.get(url, params={"review_status": "pending", "page_size": 1}).json()["total"] == 1
    assert client.get(url, params={"page": 2, "page_size": 1}).json()["items"] == []
    assert client.get(url, params={"review_status": "confirmed"}).json()["items"] == []
    assert client.get(url, params={"page_size": 101}).status_code == 422
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(url).status_code == 404
        assert client.get(f"/api/v1/projects/{project}/governance").status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    db_session.get(Project, uuid.UUID(project)).archived_at = utc_now()
    db_session.commit()
    assert client.get(url).status_code == 404
    assert resolve(client, project, change).status_code == 404


def test_governance_is_bounded_deterministic_and_read_only(client, db_session, configured, monkeypatch):
    project, old, new = pair(client, monkeypatch)
    third = reviewed_decision(client, monkeypatch, project, 3, name=" STORAGE   decision ", summary=new["entity"]["summary"])
    db_session.get(KnowledgeEvidence, uuid.UUID(old["evidence"][0]["id"])).quote = "not in the source"
    db_session.commit()
    before = copy.deepcopy([(row.id, row.status, row.valid_from, row.valid_to) for row in db_session.scalars(select(KnowledgeEntity))])
    url = f"/api/v1/projects/{project}/governance"
    result = client.get(url).json()
    assert result["scanned_entity_count"] == 3 and not result["truncated"]
    assert {item["kind"] for item in result["findings"]} >= {"missing_evidence", "possible_conflict", "orphan"}
    assert client.get(url).json()["findings"] == result["findings"]
    limited = client.get(url, params={"limit": 1}).json()
    assert len(limited["findings"]) == 1 and limited["truncated"]
    assert db_session.scalar(select(func.count()).select_from(KnowledgeChange)) == 0
    assert [(row.id, row.status, row.valid_from, row.valid_to) for row in db_session.scalars(select(KnowledgeEntity))] == before
    assert client.get(url, params={"limit": 501}).status_code == 422


def test_duplicate_governance_checks_literal_quotes_and_no_writes(client, configured, monkeypatch):
    project, old, new = pair(client, monkeypatch)
    reviewed_decision(client, monkeypatch, project, 3, name="storage decision", summary=old["entity"]["summary"])
    result = client.get(f"/api/v1/projects/{project}/governance").json()
    assert "duplicate" in {item["kind"] for item in result["findings"]}


def test_old_endpoint_edges_are_hidden_now_but_preserved_historically(client, configured, monkeypatch):
    project, _, candidates = extracted(client, monkeypatch)
    confirmed = [confirm(client, item) for item in candidates]
    old_id = next(item["knowledge_id"] for item in confirmed if item["type"] == "Decision")
    old = client.get(f"/api/v1/knowledge/entities/{old_id}").json()
    new = reviewed_decision(client, monkeypatch, project, 2)
    change = propose(client, project, proposal(old, new))
    assert resolve(client, project, change).status_code == 200
    url = f"/api/v1/projects/{project}/graph"
    assert not client.get(url).json()["edges"]
    from datetime import datetime
    at = (datetime.fromisoformat(change["effective_at"].replace("Z", "+00:00")) - timedelta(microseconds=1)).isoformat()
    historical = client.get(url, params={"valid_at": at}).json()
    assert len(historical["edges"]) == 1
    assert historical["edges"][0]["source_id"] == old_id


def test_evidence_is_revalidated_at_confirmation_and_history_reports_truncation(client, db_session, configured, monkeypatch):
    project, old, new = pair(client, monkeypatch)
    data = proposal(old, new)
    change = propose(client, project, data)
    evidence = db_session.get(KnowledgeEvidence, uuid.UUID(data["evidence_id"]))
    original = evidence.quote
    evidence.quote = "invalidated after proposing"
    db_session.commit()
    assert resolve(client, project, change).status_code == 409
    evidence.quote = original
    db_session.commit()
    assert resolve(client, project, change).status_code == 200
    third = reviewed_decision(client, monkeypatch, project, 3)
    assert resolve(client, project, propose(client, project, proposal(new, third))).status_code == 200
    monkeypatch.setattr(evolution, "MAX_HISTORY_ENTITIES", 2)
    result = client.get(f"/api/v1/projects/{project}/knowledge/entities/{third['entity']['id']}/history").json()
    assert result["truncated"] and len(result["entities"]) == 2
    monkeypatch.setattr(evolution, "MAX_GOVERNANCE_ENTITIES", 0)
    assert client.get(f"/api/v1/projects/{project}/governance").json()["truncated"]


@pytest.mark.parametrize("field,value", [("reason", "  "), ("kind", "USES"), ("effective_at", "2026-10-23T01:00:00"),
                                         ("user_id", "forged")])
def test_change_schema_rejects_untrusted_fields(client, configured, monkeypatch, field, value):
    project, old, new = pair(client, monkeypatch)
    assert client.post(f"/api/v1/projects/{project}/knowledge-changes", json=proposal(old, new, **{field: value})).status_code == 422
