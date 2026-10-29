from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.schema_version import EXPECTED_REVISION


def test_readiness_expected_revision_tracks_migration_head():
    from pathlib import Path
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / 'alembic.ini'))
    config.set_main_option('script_location', str(root / 'migrations'))
    assert ScriptDirectory.from_config(config).get_current_head() == EXPECTED_REVISION


def test_liveness(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Knowledge Atlas API",
    }
    assert response.headers["X-Request-ID"]


def stamp(db_session, revision=EXPECTED_REVISION):
    db_session.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)'))
    db_session.execute(text('INSERT INTO alembic_version (version_num) VALUES (:revision)'), {'revision':revision})
    db_session.commit()


def test_readiness_requires_current_schema(client: TestClient, db_session) -> None:
    stamp(db_session)
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {
            "postgresql": {"status": "up", "detail": None},
            "schema": {"status": "up", "detail": None},
        },
    }


def test_readiness_refuses_unmigrated_and_behind_database(client, db_session):
    result=client.get('/api/v1/health/ready')
    assert result.status_code==503 and result.json()['dependencies']['postgresql']['status']=='up'
    stamp(db_session,'20261026_0017')
    result=client.get('/api/v1/health/ready')
    assert result.status_code==503 and '20261026_0018' in result.json()['dependencies']['schema']['detail']


def test_readiness_refuses_falsely_stamped_incomplete_schema(client, db_session, monkeypatch):
    from app.core import schema_version
    stamp(db_session)
    actual=schema_version.inspect(db_session.connection())
    class MissingTable:
        default_schema_name=actual.default_schema_name
        def get_table_names(self, **kwargs):
            return [name for name in actual.get_table_names(**kwargs) if name!='conversations']
    monkeypatch.setattr(schema_version,'inspect',lambda _:MissingTable())
    result=client.get('/api/v1/health/ready')
    assert result.status_code==503 and 'incomplete' in result.json()['dependencies']['schema']['detail']


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

