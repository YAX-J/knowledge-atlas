from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


def test_liveness(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Knowledge Atlas API",
    }
    assert response.headers["X-Request-ID"]


def test_readiness_requires_only_postgresql(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {
            "postgresql": {"status": "up", "detail": None},
        },
    }


def test_readiness_reports_database_failure_without_connection_details(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    def fail_execute(*args, **kwargs):
        raise OperationalError(
            "SELECT 1", {}, Exception("private connection details")
        )

    monkeypatch.setattr(db_session, "execute", fail_execute)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "dependencies": {
            "postgresql": {
                "status": "down",
                "detail": "database connection failed",
            },
        },
    }

