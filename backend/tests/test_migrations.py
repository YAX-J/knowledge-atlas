from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.core import config as app_config
from app.models.domain import ProcessingTask, Project, SourceDocument, TaskStatus


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
    assert "ck_tasks_attempt_count" in sql
    assert "lease_expires_at" in sql
    assert "CREATE TABLE review_events" in sql
    assert "ck_review_events_action" in sql
    assert "CREATE TABLE knowledge_entities" in sql
    assert "fk_relationship_source_scope" in sql
    assert "CREATE TABLE knowledge_evidence" in sql
    assert "CREATE TABLE knowledge_embeddings" in sql
    assert "VECTOR(1024)" in sql


def test_lease_migration_preserves_legacy_running_tasks(tmp_path, monkeypatch) -> None:
    url = f"sqlite+pysqlite:///{(tmp_path / 'leases.db').as_posix()}"
    monkeypatch.setattr(app_config, "get_settings", lambda: SimpleNamespace(database_url=url))
    config = migration_config()
    command.upgrade(config, "20261017_0002")
    engine = create_engine(url)
    user_id, project_id, source_id, task_id = [uuid.uuid4() for _ in range(4)]
    with Session(engine) as db:
        db.add(Project(id=project_id, user_id=user_id, name="Existing project"))
        db.flush()
        db.add(SourceDocument(
            id=source_id, user_id=user_id, project_id=project_id,
            original_name="old.md", source_type="markdown", media_type="text/markdown",
            size_bytes=4, content_sha256="0" * 64, content="Note",
        ))
        db.commit()
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO processing_tasks (id, user_id, project_id, source_id, type, status, stage, progress) "
            "VALUES (:id, :user_id, :project_id, :source_id, 'knowledge_extraction', 'running', 'parsing', 0)"
        ), {"id": task_id.hex, "user_id": user_id.hex,
            "project_id": project_id.hex, "source_id": source_id.hex})
    command.upgrade(config, "head")
    with Session(engine) as db:
        task = db.get(ProcessingTask, task_id)
        assert task.status == TaskStatus.RUNNING and task.attempt_count == 0
        assert task.execution_id is None and task.lease_expires_at is None
    command.downgrade(config, "20261017_0002")
    assert "attempt_count" not in {column["name"] for column in inspect(engine).get_columns("processing_tasks")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM processing_tasks")).scalar_one() == "running"
    command.upgrade(config, "head")
    engine.dispose()


def test_graph_migration_preserves_reviewed_candidates_and_is_reversible(tmp_path, monkeypatch):
    from app.models.domain import CandidateKnowledge, ReviewStatus, SourceChunk
    from app.models.graph import KnowledgeEntity, KnowledgeEvidence
    url = f"sqlite+pysqlite:///{(tmp_path / 'graph.db').as_posix()}"
    monkeypatch.setattr(app_config, "get_settings", lambda: SimpleNamespace(database_url=url))
    config = migration_config()
    command.upgrade(config, "20261017_0004")
    engine = create_engine(url)
    candidate_id, chunk_id = uuid.uuid4(), uuid.uuid4()
    with Session(engine) as db:
        project = Project(user_id=uuid.uuid4(), name="Legacy project")
        db.add(project)
        db.flush()
        source = SourceDocument(user_id=project.user_id, project_id=project.id, original_name="note.md",
                                source_type="markdown", media_type="text/markdown", size_bytes=4, content_sha256="0"*64, content="Note")
        db.add(source)
        db.flush()
        task = ProcessingTask(user_id=project.user_id, project_id=project.id, source_id=source.id, type="knowledge_candidates")
        db.add(task)
        db.flush()
        db.add(SourceChunk(id=chunk_id, user_id=project.user_id, project_id=project.id, source_id=source.id,
                           position=0, kind="paragraph", heading_path=[], content="Note", content_sha256="0"*64, start_line=1, end_line=1))
        db.add(CandidateKnowledge(id=candidate_id, user_id=project.user_id, project_id=project.id, source_id=source.id,
                                 task_id=task.id, name="Existing", summary="Kept", candidate_type="Concept", confidence=.8,
                                 payload={}, review_status=ReviewStatus.CONFIRMED))
        db.commit()
    command.upgrade(config, "head")
    assert {"knowledge_entities", "knowledge_relationships", "knowledge_evidence", "knowledge_embeddings"} <= set(inspect(engine).get_table_names())
    with Session(engine) as db:
        from app.models.domain import utc_now
        candidate = db.get(CandidateKnowledge, candidate_id)
        formal_id = uuid.uuid4()
        db.add(KnowledgeEntity(id=formal_id, candidate_id=candidate_id, user_id=candidate.user_id,
                               project_id=candidate.project_id, type="Concept", name="Existing", summary="Kept",
                               confidence=.8, status="active", valid_from=utc_now()))
        db.flush()
        db.add(KnowledgeEvidence(id=uuid.uuid4(), user_id=candidate.user_id, project_id=candidate.project_id,
                                entity_id=formal_id, source_id=candidate.source_id, chunk_id=chunk_id,
                                quote="Note", start_line=1, end_line=1, heading_path=[]))
        db.commit()
    command.downgrade(config, "20261017_0004")
    assert "knowledge_entities" not in inspect(engine).get_table_names()
    with Session(engine) as db:
        assert db.get(CandidateKnowledge, candidate_id).review_status == ReviewStatus.CONFIRMED
        assert db.get(SourceChunk, chunk_id).content == "Note"
    command.upgrade(config, "head")
    engine.dispose()


def test_review_migration_preserves_existing_candidates(tmp_path, monkeypatch) -> None:
    from app.models.domain import CandidateKnowledge, ReviewEvent, ReviewStatus
    url = f"sqlite+pysqlite:///{(tmp_path / 'reviews.db').as_posix()}"
    monkeypatch.setattr(app_config, "get_settings", lambda: SimpleNamespace(database_url=url))
    config = migration_config()
    command.upgrade(config, "20261017_0003")
    engine = create_engine(url)
    candidate_id = uuid.uuid4()
    with Session(engine) as db:
        user_id = uuid.uuid4()
        project = Project(user_id=user_id, name="Existing project")
        db.add(project)
        db.flush()
        source = SourceDocument(user_id=user_id, project_id=project.id, original_name="old.md",
                                source_type="markdown", media_type="text/markdown", size_bytes=4,
                                content_sha256="0" * 64, content="Note")
        db.add(source)
        db.flush()
        task = ProcessingTask(user_id=user_id, project_id=project.id, source_id=source.id, type="markdown_parsing")
        db.add(task)
        db.flush()
        db.add(CandidateKnowledge(id=candidate_id, user_id=user_id, project_id=project.id,
                                 source_id=source.id, task_id=task.id, candidate_type="Concept",
                                 name="Existing", summary="Kept", confidence=.8, payload={}))
        db.commit()
    command.upgrade(config, "head")
    assert "review_events" in inspect(engine).get_table_names()
    with Session(engine) as db:
        candidate = db.get(CandidateKnowledge, candidate_id)
        assert candidate.name == "Existing" and candidate.review_status == ReviewStatus.PENDING
        db.add(ReviewEvent(candidate_id=candidate_id, user_id=candidate.user_id,
                           project_id=candidate.project_id, action="confirm", before={}, after={}))
        db.commit()
    command.downgrade(config, "20261017_0003")
    assert "review_events" not in inspect(engine).get_table_names()
    with Session(engine) as db:
        assert db.get(CandidateKnowledge, candidate_id).summary == "Kept"
    command.upgrade(config, "head")
    engine.dispose()
