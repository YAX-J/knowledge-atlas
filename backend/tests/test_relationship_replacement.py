import json
import uuid

from sqlalchemy import select

from app.api.routes import agents
from app.models.domain import ReviewEvent
from app.services import deepseek
from tests.test_knowledge import configured
from tests.test_multi_agent import tool
from tests.test_sources import create_project


def test_reviewed_primary_database_replacement_preserves_history(client, db_session, configured, monkeypatch):
    project = create_project(client)
    base = f"/api/v1/projects/{project}"
    monkeypatch.setattr(agents, "get_settings", lambda: configured)

    def extract(database, start, *, fact_slot=True):
        quote = f"{start} 起，订单服务的主数据库使用 {database}。"
        note = client.post(f"{base}/notes", json={
            "request_id": str(uuid.uuid4()), "title": f"订单服务数据库记录 · {database}", "markdown": quote,
        }).json()["current"]

        def turn(_settings, messages, _tools, **_kwargs):
            message = messages[-1]
            data = json.loads(message["content"])
            if message["role"] == "user":
                return tool("read_chunk", {"chunk_id": data["chunks"][-1]["chunk_id"]})
            shared = dict(summary=quote, confidence=.9, temporal={"start": start},
                          evidence=[dict(chunk_id=data["chunk_id"], quote=quote)])
            relation = dict(local_id="uses", type="USES", source="service", target="database", **shared)
            if fact_slot:
                relation["fact_slot"] = "primary_database"
            return {"content": json.dumps(dict(entities=[
                dict(local_id="service", type="Project", name="订单服务", **shared),
                dict(local_id="database", type="Technology", name=database, **shared),
            ], relations=[relation]))}

        monkeypatch.setattr(deepseek, "call_agent_turn", turn)
        response = client.post(f"{base}/agent-runs", json=dict(
            request_id=str(uuid.uuid4()), kind="knowledge_pipeline", note_revision_id=note["id"],
        ))
        assert response.status_code == 200, response.text
        run = response.json()
        assert run["status"] == "awaiting_review", run
        source_id = run["source_id"]
        items = client.get(f"{base}/reviews", params={"source_id": source_id}).json()["items"]
        relation = next(item for item in items if item["kind"] == "relation")
        entities = [item["id"] for item in items if item["kind"] == "entity"]
        return source_id, relation, entities, quote

    def confirm_batch(source_id, identifiers):
        return client.post(f"{base}/reviews/resolve-batch", json=dict(
            source_id=source_id, review_ids=identifiers, action="confirm",
        ))

    old_source, old, old_entities, old_quote = extract("MySQL", "2026-03-01", fact_slot=False)
    assert old["replacement"] is None
    assert confirm_batch(old_source, [*old_entities, old["id"]]).status_code == 200
    new_source, new, new_entities, new_quote = extract("PostgreSQL", "2026-06-01")
    proposal = new["replacement"]
    assert proposal["effective_at"] == "2026-06-01T00:00:00Z"
    assert proposal["evidence"][0]["quote"] == old_quote
    assert new["evidence"][0]["quote"] == new_quote
    assert confirm_batch(new_source, [*new_entities, new["id"]]).json()["error"]["code"] == "REVIEW_REPLACEMENT_REQUIRED"
    assert {item["review_status"] for item in client.get(f"{base}/reviews", params={"source_id": new_source}).json()["items"]} == {"pending"}
    assert confirm_batch(new_source, new_entities).status_code == 200
    # Approvals pin the final endpoint names and both publications' evidence.
    new = next(item for item in client.get(f"{base}/reviews", params={"source_id": new_source}).json()["items"]
               if item["kind"] == "relation")
    approval = new["replacement"]["approval"]
    resolve = f"/api/v1/reviews/{new['id']}/resolve"
    wrong_approval = {**approval, "token": "0" * 64}
    assert client.post(resolve, json=dict(action="confirm", replacement=wrong_approval)).json()["error"]["code"] == "REVIEW_REPLACEMENT_STALE"
    approved = client.post(resolve, json=dict(action="confirm", replacement=approval))
    assert approved.status_code == 200, approved.text
    assert approved.json()["supersedes_relationship_id"] == approval["old_relationship_id"]
    assert client.post(resolve, json=dict(action="confirm", replacement=approval)).json() == approved.json()
    audit = db_session.scalars(select(ReviewEvent).where(ReviewEvent.candidate_id == uuid.UUID(new["id"]))).one()
    assert audit.after["replacement"]["kind"] == "SUPERSEDES"
    assert audit.after["replacement"]["old"]["valid_to"] == "2026-06-01T00:00:00Z"

    def edge_at(instant):
        graph = client.get(f"{base}/graph", params={"valid_at": instant}).json()
        edge, = graph["edges"]
        detail = client.get(f"/api/v1/knowledge/relationships/{edge['id']}", params={"valid_at": instant}).json()
        return edge, detail["evidence"][0]

    old_edge, evidence = edge_at("2026-04-01T00:00:00Z")
    assert evidence["quote"] == old_quote and evidence["source_id"] == old_source
    assert old_edge["status"] == "superseded"
    new_edge, evidence = edge_at("2026-06-01T00:00:00Z")
    assert evidence["quote"] == new_quote and evidence["source_id"] == new_source
    assert old_edge["source_id"] == new_edge["source_id"]
