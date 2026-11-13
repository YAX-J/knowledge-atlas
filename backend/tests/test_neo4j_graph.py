from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from neo4j.exceptions import ServiceUnavailable

from app.api.routes import graph as graph_routes
from app.core.config import Settings
from app.core.errors import AppError
from app.models.domain import utc_now
from app.schemas.graph import GraphRead
from app.services import neo4j_graph
from tests.test_graph import confirm, extracted
from tests.test_knowledge import configured


def test_neo4j_health_checks_the_configured_database(client, monkeypatch):
    monkeypatch.setattr(graph_routes, "get_settings", lambda: Settings(_env_file=None, neo4j_password=None))
    url = "/api/v1/health/neo4j"
    assert client.get(url).json()["error"]["code"] == "NEO4J_NOT_CONFIGURED"

    settings = Settings(_env_file=None, neo4j_password="example-password", neo4j_database="example-db")
    monkeypatch.setattr(graph_routes, "get_settings", lambda: settings)
    driver = MagicMock()
    driver.__enter__.return_value = driver
    session = driver.session.return_value.__enter__.return_value
    monkeypatch.setattr(neo4j_graph.GraphDatabase, "driver", lambda *args, **kwargs: driver)

    assert client.get(url).json() == {"status": "up"}
    driver.session.assert_called_with(database="example-db")
    assert str(session.run.call_args.args[0]) == "RETURN 1 AS ok"
    session.run.side_effect = ServiceUnavailable("private connection details")
    response = client.get(url)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NEO4J_UNAVAILABLE"
    assert "private connection details" not in response.text


def test_sync_exports_visible_confirmed_graph_and_checks_scope(client, configured, monkeypatch):
    project_id, _, candidates = extracted(client, monkeypatch)
    for candidate in candidates:
        confirm(client, candidate)
    expected = client.get(f"/api/v1/projects/{project_id}/graph").json()
    driver = MagicMock()
    driver.__enter__.return_value = driver
    session = driver.session.return_value.__enter__.return_value
    driver_factory = MagicMock(return_value=driver)
    monkeypatch.setattr(neo4j_graph, "_driver", driver_factory)

    assert client.post(f"/api/v1/projects/{uuid4()}/graph/neo4j/sync").status_code == 404
    driver_factory.assert_not_called()

    url = f"/api/v1/projects/{project_id}/graph/neo4j/sync"
    response = client.post(url)
    assert response.status_code == 200, response.text
    assert response.json()["node_count"] == 2
    assert response.json()["edge_count"] == 1
    callback, scope, projection, _, _ = session.execute_write.call_args.args
    assert callback is neo4j_graph._replace_snapshot
    assert scope["project_id"] == project_id
    assert projection.model_dump(mode="json") == expected

    earliest = "2000-01-01T00:00:00Z"
    response = client.post(url, params={"valid_at": earliest})
    assert response.status_code == 200
    assert response.json() == {"valid_at": earliest, "node_count": 0, "edge_count": 0}

    session.execute_read.return_value = {**expected, "valid_at": earliest}
    response = client.get(url.removesuffix("/sync"), params={"types": "Concept", "depth": 2, "limit": 3})
    assert response.status_code == 200
    assert response.json() == {**expected, "valid_at": earliest}
    callback, read_scope, center_id, depth, types, limit = session.execute_read.call_args.args
    assert callback is neo4j_graph._read_snapshot and read_scope == scope
    assert (center_id, depth, types, limit) == (None, 2, ["Concept"], 3)


def test_snapshot_read_restores_omitted_validity_and_applies_neighborhood_limit():
    now = utc_now().isoformat()
    scope = {"user_id": str(uuid4()), "project_id": str(uuid4())}

    def node(name):
        return {"id": str(uuid4()), "candidate_id": str(uuid4()), "project_id": scope["project_id"],
                "name": name, "type": "Concept", "summary": name, "confidence": 1,
                "status": "active", "valid_from": now}

    center, neighbor, extra = (node(name) for name in ("center", "neighbor", "extra"))
    edge = {**node("edge"), "source_id": center["id"], "target_id": neighbor["id"]}
    tx = MagicMock()
    tx.run.side_effect = [
        SimpleNamespace(single=lambda: {"valid_at": now}),
        SimpleNamespace(single=lambda: {"node": center}),
        SimpleNamespace(value=lambda _: [neighbor, extra]),
        SimpleNamespace(value=lambda _: [edge]),
    ]
    result = neo4j_graph._read_snapshot(tx, scope, center["id"], 1, ["Concept"], 2)
    assert [node.name for node in result.nodes] == ["center", "neighbor"]
    assert result.nodes[0].valid_to is None and result.edges[0].valid_to is None
    assert result.truncated
    assert tx.run.call_args_list[2].kwargs["limit"] == 2
    assert tx.run.call_args_list[3].kwargs["ids"] == [center["id"], neighbor["id"]]


def test_snapshot_requires_sync_and_does_not_publish_missing_edge_endpoints():
    tx = MagicMock()
    tx.run.return_value.single.return_value = None
    scope = {"project_id": str(uuid4()), "user_id": str(uuid4())}
    with pytest.raises(AppError, match="请先同步"):
        neo4j_graph._read_snapshot(tx, scope, None, 1, [], 10)

    tx.reset_mock()
    edge = {"id": uuid4(), "project_id": scope["project_id"], "candidate_id": uuid4(),
            "type": "DEPENDS_ON", "name": "edge", "summary": "edge", "confidence": 1,
            "status": "active", "valid_from": utc_now(), "valid_to": None,
            "source_id": uuid4(), "target_id": uuid4()}
    projection = GraphRead(nodes=[], edges=[edge], truncated=False)
    tx.run.return_value.single.return_value = {"written": 0}
    with pytest.raises(AppError, match="缺失端点"):
        neo4j_graph._replace_snapshot(tx, scope, projection, utc_now(), uuid4().hex)
    assert all("MERGE (p:" not in call.args[0] for call in tx.run.call_args_list)
