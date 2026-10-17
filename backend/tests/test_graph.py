import copy
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import get_current_user_id
from app.core.errors import AppError
from app.main import app
from app.models.domain import CandidateKnowledge, Project, ReviewEvent, ReviewStatus, utc_now
from app.models.graph import KnowledgeEntity, KnowledgeEvidence, KnowledgeRelationship
from app.schemas.knowledge import ExtractionDraft
from app.services import deepseek, graph
from tests.test_knowledge import configured, parsed_source, reviews


def extracted(client, monkeypatch, draft_override=None):
    project_id, source, draft = parsed_source(client)
    if draft_override:
        draft = draft_override(draft)
    monkeypatch.setattr(deepseek, "extract_candidates", lambda *_: ExtractionDraft.model_validate(draft))
    response = client.post(f"/api/v1/sources/{source['source_id']}/extract")
    assert response.json()["task"]["status"] == "succeeded"
    return project_id, source, reviews(client, project_id)["items"]


def confirm(client, candidate):
    response = client.post(f"/api/v1/reviews/{candidate['id']}/resolve", json={"action": "confirm"})
    assert response.status_code == 200, response.text
    return response.json()


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_confirmation_persists_graph_and_locatable_evidence(client, db_session, configured, monkeypatch):
    project_id, source, items = extracted(client, monkeypatch)
    url = f"/api/v1/projects/{project_id}/graph"
    assert client.get(url).json() == {"nodes": [], "edges": [], "truncated": False}
    confirmed = [confirm(client, item) for item in items]
    result = client.get(url)
    assert result.status_code == 200
    data = result.json()
    assert len(data["nodes"]) == 2 and len(data["edges"]) == 1
    assert {item["knowledge_id"] for item in confirmed} == {node["id"] for node in [*data["nodes"], *data["edges"]]}
    assert not {"user_id", "x", "y"} & data["nodes"][0].keys()
    assert data["edges"][0]["source_id"] in {node["id"] for node in data["nodes"]}
    assert data["edges"][0]["target_id"] in {node["id"] for node in data["nodes"]}
    for node in data["nodes"]:
        assert node["evidence_count"] == 1
        detail = client.get(f"/api/v1/knowledge/entities/{node['id']}").json()
        assert detail["entity"] == node and len(detail["relationships"]) == 1
        evidence = detail["evidence"][0]
        assert evidence["source_id"] == source["source_id"]
        assert evidence["title"] == "note.md" and evidence["start_line"] == 3
        assert evidence["quote"] == "Use PostgreSQL for storage."
        assert evidence["uri"].startswith("project://") and "file://" not in str(detail)
    edge_detail = client.get(f"/api/v1/knowledge/relationships/{data['edges'][0]['id']}")
    assert edge_detail.status_code == 200 and len(edge_detail.json()["evidence"]) == 1
    for item in items:
        confirm(client, item)
    assert count(db_session, KnowledgeEntity) == 2
    assert count(db_session, KnowledgeRelationship) == 1
    assert count(db_session, KnowledgeEvidence) == 3
    assert count(db_session, ReviewEvent) == 3


def chain_draft(draft):
    prototype = draft["entities"][0]
    draft["entities"] = [{**copy.deepcopy(prototype), "local_id": key, "name": key.upper(), "type": kind}
                         for key, kind in [("a", "Decision"), ("b", "Technology"), ("c", "Concept"), ("d", "Concept")]]
    relation = draft["relations"][0]
    draft["relations"] = [{**copy.deepcopy(relation), "local_id": f"r{index}", "source": source, "target": target}
                          for index, (source, target) in enumerate([("a", "b"), ("b", "c"), ("c", "d"), ("d", "c"), ("c", "c")])]
    return draft


def test_neighborhood_limits_filters_cycles_and_validity(client, db_session, configured, monkeypatch):
    project_id, _, items = extracted(client, monkeypatch, chain_draft)
    entities = [item for item in items if item["kind"] == "entity"]
    others = [item for item in items if item["kind"] == "relation"]
    for item in entities + others:
        confirm(client, item)
    url = f"/api/v1/projects/{project_id}/graph"
    all_nodes = client.get(url).json()["nodes"]
    center = next(item["id"] for item in all_nodes if item["name"] == "A")
    assert {item["name"] for item in client.get(url, params={"center_id": center, "depth": 1}).json()["nodes"]} == {"A", "B"}
    assert {item["name"] for item in client.get(url, params={"center_id": center, "depth": 2}).json()["nodes"]} == {"A", "B", "C"}
    limited = client.get(url, params={"center_id": center, "limit": 1}).json()
    assert limited["truncated"] and len(limited["nodes"]) == 1 and not limited["edges"]
    assert client.get(url, params={"limit": 2}).json()["truncated"]
    assert {item["name"] for item in client.get(url, params={"types": "Technology"}).json()["nodes"]} == {"B"}
    before = (utc_now() - timedelta(days=1)).isoformat()
    assert client.get(url, params={"valid_at": before}).json()["nodes"] == []
    assert client.get(f"/api/v1/knowledge/entities/{center}", params={"valid_at": before}).status_code == 404
    for params in [{"depth": 3}, {"limit": 201}, {"types": "Invented"}, {"valid_at": "2026-10-17T00:00:00"}]:
        assert client.get(url, params=params).status_code == 422
    assert client.get(url, params={"center_id": str(uuid.uuid4())}).status_code == 404
    b = db_session.scalar(select(KnowledgeEntity).where(KnowledgeEntity.name == "B"))
    b.status = "archived"
    db_session.commit()
    data = client.get(url).json()
    assert "B" not in {item["name"] for item in data["nodes"]}
    ids = {item["id"] for item in data["nodes"]}
    assert all(item["source_id"] in ids and item["target_id"] in ids for item in data["edges"])
    monkeypatch.setattr(graph, "MAX_EDGES", 1)
    bounded = client.get(url).json()
    assert bounded["truncated"] and len(bounded["edges"]) == 1


def test_legacy_confirmed_candidates_can_be_promoted_without_duplicate_audit(client, db_session, configured, monkeypatch):
    project_id, _, items = extracted(client, monkeypatch)
    for item in items:
        candidate = db_session.get(CandidateKnowledge, uuid.UUID(item["id"]))
        candidate.review_status = ReviewStatus.CONFIRMED
        db_session.add(ReviewEvent(candidate_id=candidate.id, user_id=candidate.user_id,
                                  project_id=candidate.project_id, action="confirm", before={}, after={}))
    db_session.commit()
    assert all(item["knowledge_id"] is None for item in reviews(client, project_id)["items"])
    relation = next(item for item in items if item["kind"] == "relation")
    first = confirm(client, relation)
    assert first["knowledge_id"] and count(db_session, KnowledgeEntity) == 2
    assert confirm(client, relation) == first
    assert count(db_session, ReviewEvent) == 3
    assert count(db_session, KnowledgeEvidence) == 3


def test_promotion_failure_rolls_back_review_audit_and_formal_writes(client, db_session, configured, monkeypatch):
    project_id, _, items = extracted(client, monkeypatch)
    item = next(item for item in items if item["kind"] == "entity")
    original = graph.promote_candidate
    def fail_after_write(*args, **kwargs):
        original(*args, **kwargs)
        raise AppError(status_code=409, code="TEST_PROMOTION_FAILED", message="Simulated failure")
    monkeypatch.setattr(graph, "promote_candidate", fail_after_write)
    response = client.post(f"/api/v1/reviews/{item['id']}/resolve", json={"action": "confirm", "changes": {"name": "Changed"}})
    assert response.status_code == 409
    candidate = db_session.get(CandidateKnowledge, uuid.UUID(item["id"]))
    assert candidate.review_status == ReviewStatus.PENDING and candidate.name == item["name"]
    assert count(db_session, ReviewEvent) == count(db_session, KnowledgeEntity) == count(db_session, KnowledgeEvidence) == 0


def test_revalidation_rejection_and_scope_boundaries(client, db_session, configured, monkeypatch):
    project_id, _, items = extracted(client, monkeypatch)
    item = next(item for item in items if item["kind"] == "entity")
    candidate = db_session.get(CandidateKnowledge, uuid.UUID(item["id"]))
    original_payload = copy.deepcopy(candidate.payload)
    candidate.payload = {**candidate.payload, "evidence": [{"chunk_id": str(uuid.uuid4()), "quote": "Foreign evidence"}]}
    db_session.commit()
    assert client.post(f"/api/v1/reviews/{item['id']}/resolve", json={"action": "confirm"}).status_code == 409
    assert count(db_session, KnowledgeEntity) == 0
    candidate.payload = original_payload
    db_session.commit()
    node_id = confirm(client, item)["knowledge_id"]
    rejected = next(value for value in items if value["kind"] == "entity" and value["id"] != item["id"])
    assert client.post(f"/api/v1/reviews/{rejected['id']}/resolve", json={"action": "reject"}).status_code == 200
    assert count(db_session, KnowledgeEntity) == 1
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(f"/api/v1/projects/{project_id}/graph").status_code == 404
        assert client.get(f"/api/v1/knowledge/entities/{node_id}").status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)
    project = db_session.get(Project, uuid.UUID(project_id))
    project.archived_at = utc_now()
    db_session.commit()
    assert client.get(f"/api/v1/projects/{project_id}/graph").status_code == 404
    assert client.get(f"/api/v1/knowledge/entities/{node_id}").status_code == 404


def test_database_rejects_cross_project_relationship_endpoints(client, db_session, configured, monkeypatch):
    project_id, _, items = extracted(client, monkeypatch)
    for item in items:
        confirm(client, item)
    db_session.commit()
    db_session.connection().exec_driver_sql("PRAGMA foreign_keys=ON")
    assert db_session.connection().exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    edge = db_session.scalar(select(KnowledgeRelationship))
    other = Project(user_id=edge.user_id, name="Other")
    db_session.add(other)
    db_session.flush()
    db_session.add(KnowledgeRelationship(
        id=uuid.uuid4(), user_id=edge.user_id, project_id=other.id,
        candidate_id=db_session.scalar(select(KnowledgeEntity.candidate_id).limit(1)),
        source_id=edge.source_id, target_id=edge.target_id, type="USES", name="Invalid", summary="Invalid",
        confidence=.9, status="active", valid_from=utc_now(),
    ))
    with pytest.raises(IntegrityError) as error:
        db_session.flush()
    assert "FOREIGN KEY" in str(error.value)
    db_session.rollback()
