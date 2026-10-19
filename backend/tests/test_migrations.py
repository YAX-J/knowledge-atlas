from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.core import config as app_config
from app.models.domain import (
    ProcessingTask,
    Project,
    SourceDocument,
    SourceRepository,
    TaskStatus,
)


def migration_config() -> Config:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return config


def insert_legacy_source(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    source_id: uuid.UUID | None = None,
    original_name: str = "old.md",
) -> uuid.UUID:
    source_id = source_id or uuid.uuid4()
    db.execute(SourceDocument.__table__.insert().values(
        id=source_id,
        user_id=user_id,
        project_id=project_id,
        original_name=original_name,
        source_type="markdown",
        media_type="text/markdown",
        size_bytes=4,
        content_sha256="0" * 64,
        content="Note",
    ))
    return source_id


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
        insert_legacy_source(
            db, source_id=source_id, user_id=project.user_id, project_id=project.id
        )
        db.commit()
    command.upgrade(config, "head")
    assert "source_chunks" in inspect(engine).get_table_names()
    assert inspect(engine).get_unique_constraints("source_chunks")[0]["column_names"] == ["source_id", "position"]
    with Session(engine) as db:
        assert db.scalar(select(SourceDocument.content).where(SourceDocument.id == source_id)) == "Note"
    command.downgrade(config, "20261017_0001")
    assert "source_chunks" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT content FROM source_documents WHERE id = :id"),
            {"id": source_id.hex},
        ).scalar_one() == "Note"
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
    assert "ADD COLUMN relative_path VARCHAR(1024)" in sql
    assert "CREATE TABLE source_repositories" in sql
    assert "ck_source_repositories_kind" in sql
    assert "uq_source_repositories_scope_name" in sql
    assert "ix_sources_repository_dedupe" in sql
    assert "repository_id UUID" in sql
    assert "remote_url VARCHAR(1024)" in sql
    assert "ck_source_repositories_remote_identity" in sql
    assert "uq_source_repositories_remote_scope" in sql


def test_github_repository_migration_preserves_local_repositories_and_is_reversible(
    tmp_path, monkeypatch
) -> None:
    url = f"sqlite+pysqlite:///{(tmp_path / 'github-repositories.db').as_posix()}"
    monkeypatch.setattr(
        app_config, "get_settings", lambda: SimpleNamespace(database_url=url)
    )
    config = migration_config()
    command.upgrade(config, "20261019_0008")
    engine = create_engine(url)
    repository_id = uuid.uuid4()
    with Session(engine) as db:
        project = Project(user_id=uuid.uuid4(), name="GitHub migration")
        db.add(project)
        db.flush()
        db.execute(SourceRepository.__table__.insert().values(
            id=repository_id,
            user_id=project.user_id,
            project_id=project.id,
            name="local-root",
            kind="local_folder",
        ))
        db.commit()

    command.upgrade(config, "head")
    repository_columns = {
        column["name"]
        for column in inspect(engine).get_columns("source_repositories")
    }
    assert {"provider", "remote_owner", "remote_name", "remote_url"} <= (
        repository_columns
    )
    with Session(engine) as db:
        repository = db.get(SourceRepository, repository_id)
        assert repository is not None and repository.remote_url is None
        repository.provider = "github"
        repository.remote_owner = "example"
        repository.remote_name = "local-root"
        repository.remote_url = "https://github.com/example/local-root"
        db.add(SourceRepository(
            user_id=repository.user_id,
            project_id=repository.project_id,
            name="example/remote-only",
            kind="git_remote",
            provider="github",
            remote_owner="example",
            remote_name="remote-only",
            remote_url="https://github.com/example/remote-only",
        ))
        db.commit()

    command.downgrade(config, "20261019_0008")
    repository_columns = {
        column["name"]
        for column in inspect(engine).get_columns("source_repositories")
    }
    assert not {
        "provider", "remote_owner", "remote_name", "remote_url"
    } & repository_columns
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT name FROM source_repositories WHERE id = :id"),
            {"id": repository_id.hex},
        ).scalar_one() == "local-root"
        assert connection.execute(
            text("SELECT COUNT(*) FROM source_repositories WHERE kind = 'git_remote'")
        ).scalar_one() == 0
    command.upgrade(config, "head")
    engine.dispose()


def test_source_repository_migration_preserves_legacy_sources_and_is_reversible(
    tmp_path, monkeypatch
) -> None:
    url = f"sqlite+pysqlite:///{(tmp_path / 'repositories.db').as_posix()}"
    monkeypatch.setattr(
        app_config, "get_settings", lambda: SimpleNamespace(database_url=url)
    )
    config = migration_config()
    command.upgrade(config, "20261019_0007")
    engine = create_engine(url)
    with Session(engine) as db:
        project = Project(user_id=uuid.uuid4(), name="Repository migration")
        db.add(project)
        db.flush()
        source_id = insert_legacy_source(
            db, user_id=project.user_id, project_id=project.id
        )
        db.commit()

    command.upgrade(config, "head")
    assert "source_repositories" in inspect(engine).get_table_names()
    assert "repository_id" in {
        column["name"] for column in inspect(engine).get_columns("source_documents")
    }
    assert "ix_sources_repository_dedupe" in {
        index["name"] for index in inspect(engine).get_indexes("source_documents")
    }
    with Session(engine) as db:
        source = db.get(SourceDocument, source_id)
        assert source is not None and source.repository_id is None
        repository = SourceRepository(
            user_id=source.user_id,
            project_id=source.project_id,
            name="legacy-root",
        )
        db.add(repository)
        db.flush()
        source.repository_id = repository.id
        db.commit()

    command.downgrade(config, "20261019_0007")
    assert "source_repositories" not in inspect(engine).get_table_names()
    assert "repository_id" not in {
        column["name"] for column in inspect(engine).get_columns("source_documents")
    }
    command.upgrade(config, "head")
    engine.dispose()


def test_source_relative_path_migration_preserves_legacy_sources_and_is_reversible(
    tmp_path, monkeypatch
) -> None:
    url = f"sqlite+pysqlite:///{(tmp_path / 'source-path.db').as_posix()}"
    monkeypatch.setattr(app_config, "get_settings", lambda: SimpleNamespace(database_url=url))
    config = migration_config()
    command.upgrade(config, "20261018_0006")
    engine = create_engine(url)
    with Session(engine) as db:
        project = Project(user_id=uuid.uuid4(), name="Path migration")
        db.add(project)
        db.flush()
        source_id = insert_legacy_source(db, user_id=project.user_id, project_id=project.id)
        db.commit()

    command.upgrade(config, "head")
    assert "relative_path" in {
        column["name"] for column in inspect(engine).get_columns("source_documents")
    }
    with Session(engine) as db:
        source = db.get(SourceDocument, source_id)
        assert source is not None and source.relative_path is None
        source.relative_path = "repository/docs/old.md"
        db.commit()

    command.downgrade(config, "20261018_0006")
    assert "relative_path" not in {
        column["name"] for column in inspect(engine).get_columns("source_documents")
    }
    command.upgrade(config, "head")
    engine.dispose()


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
        insert_legacy_source(
            db, source_id=source_id, user_id=user_id, project_id=project_id
        )
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
        source_id = insert_legacy_source(
            db, user_id=project.user_id, project_id=project.id, original_name="note.md"
        )
        task = ProcessingTask(user_id=project.user_id, project_id=project.id, source_id=source_id, type="knowledge_candidates")
        db.add(task)
        db.flush()
        db.add(SourceChunk(id=chunk_id, user_id=project.user_id, project_id=project.id, source_id=source_id,
                           position=0, kind="paragraph", heading_path=[], content="Note", content_sha256="0"*64, start_line=1, end_line=1))
        db.add(CandidateKnowledge(id=candidate_id, user_id=project.user_id, project_id=project.id, source_id=source_id,
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
        source_id = insert_legacy_source(
            db, user_id=user_id, project_id=project.id
        )
        task = ProcessingTask(user_id=user_id, project_id=project.id, source_id=source_id, type="markdown_parsing")
        db.add(task)
        db.flush()
        db.add(CandidateKnowledge(id=candidate_id, user_id=user_id, project_id=project.id,
                                 source_id=source_id, task_id=task.id, candidate_type="Concept",
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
