from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes import health


def test_liveness(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Knowledge Atlas API",
    }
    assert response.headers["X-Request-ID"]


def test_readiness_reports_database_and_optional_graph(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        health,
        "get_settings",
        lambda: SimpleNamespace(neo4j_healthcheck_enabled=False),
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {
            "postgresql": {"status": "up", "detail": None},
            "neo4j": {
                "status": "not_checked",
                "detail": "health check disabled",
            },
        },
    }

