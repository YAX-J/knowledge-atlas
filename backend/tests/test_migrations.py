from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.core import config as app_config
from app.models.domain import Project, SourceDocument


def migration_config() -> Config:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return config


def test_chunks_migration_preserves_sources_and_is_reversible(tmp_path, monkeypatch) -> None:
    url = f"sqlite+pysqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setattr(app_config, "get_settings", lambda: SimpleNamespace(database_url=url))
    config = migration_config()
    command.upgrade(config, "20261017_0001")
    engine = create_engine(url)
    source_id = uuid.uuid4()
    with Session(engine) as db:
        project = Project(user_id=uuid.uuid4(), name="Migration test")
        db.add(project)
        db.flush()
        db.add(SourceDocument(
            id=source_id, user_id=project.user_id, project_id=project.id,
            original_name="old.md", source_type="markdown", media_type="text/markdown",
            size_bytes=4, content_sha256="0" * 64, content="Note",
        ))
        db.commit()
    command.upgrade(config, "head")
    assert "source_chunks" in inspect(engine).get_table_names()
    assert inspect(engine).get_unique_constraints("source_chunks")[0]["column_names"] == ["source_id", "position"]
    with Session(engine) as db:
        assert db.scalar(select(SourceDocument.content).where(SourceDocument.id == source_id)) == "Note"
    command.downgrade(config, "20261017_0001")
    assert "source_chunks" not in inspect(engine).get_table_names()
    with Session(engine) as db:
        assert db.get(SourceDocument, source_id).content == "Note"
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()


def test_postgresql_migrations_compile_without_a_live_server(monkeypatch) -> None:
    monkeypatch.setattr(app_config, "get_settings", lambda: SimpleNamespace(
        database_url="postgresql+psycopg://localhost/knowledge_atlas"
    ))
    output = StringIO()
    config = migration_config()
    config.output_buffer = output
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE source_chunks" in sql
    assert "uq_chunks_source_position" in sql
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
