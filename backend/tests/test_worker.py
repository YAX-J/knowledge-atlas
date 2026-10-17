import hashlib
import logging
import os
import subprocess
import sys
import threading
import uuid
from contextlib import nullcontext
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from app import worker
from app.core.config import Settings
from app.core.identity import DEVELOPMENT_USER_ID
from app.db.base import Base
from app.models.domain import (
    ProcessingTask, Project, SourceChunk, SourceDocument, SourceStatus, TaskStatus, utc_now,
)
from app.services import parsing


def enqueue(db: Session, *, user_id: uuid.UUID = DEVELOPMENT_USER_ID) -> ProcessingTask:
    project = Project(user_id=user_id, name="Worker test")
    db.add(project)
    db.flush()
    content = "# Evidence\n\nKeep source locations.\n"
    source = SourceDocument(
        user_id=user_id, project_id=project.id, original_name="note.md",
        media_type="text/markdown", source_type="markdown", content=content,
        size_bytes=len(content.encode()), content_sha256=hashlib.sha256(content.encode()).hexdigest(),
    )
    db.add(source)
    db.flush()
    task = ProcessingTask(
        user_id=user_id, project_id=project.id, source_id=source.id, type="markdown_parsing"
    )
    db.add(task)
    db.commit()
    return task


def consume(db: Session) -> ProcessingTask | None:
    return worker.process_next(db, user_id=DEVELOPMENT_USER_ID, settings=Settings())


def test_worker_consumes_once_without_duplicate_chunks(db_session: Session) -> None:
    task = enqueue(db_session)
    result = consume(db_session)
    assert result.id == task.id
    assert result.status == TaskStatus.SUCCEEDED
    assert result.attempt_count == 1
    assert result.execution_id is None and result.lease_expires_at is None
    assert db_session.get(SourceDocument, task.source_id).status == SourceStatus.READY
    assert db_session.scalar(select(func.count()).select_from(SourceChunk)) == 2
    assert consume(db_session) is None
    parsing.run_task(db_session, user_id=task.user_id, task_id=task.id)
    assert task.attempt_count == 1


@pytest.mark.parametrize("legacy_lease", [False, True])
def test_worker_recovers_expired_running_task(db_session: Session, legacy_lease: bool) -> None:
    task = enqueue(db_session)
    task.status = TaskStatus.RUNNING
    task.attempt_count = 1
    task.started_at = utc_now() - timedelta(minutes=10)
    task.execution_id = None if legacy_lease else uuid.uuid4()
    task.lease_expires_at = None if legacy_lease else utc_now() - timedelta(seconds=1)
    db_session.commit()
    result = consume(db_session)
    assert result.status == TaskStatus.SUCCEEDED
    assert result.attempt_count == 2


def test_legacy_task_without_start_time_uses_update_time(db_session: Session) -> None:
    task = enqueue(db_session)
    task.status = TaskStatus.RUNNING
    task.updated_at = utc_now() - timedelta(minutes=10)
    db_session.commit()
    assert consume(db_session).status == TaskStatus.SUCCEEDED


@pytest.mark.parametrize("state", [TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED])
def test_worker_does_not_steal_live_or_retry_terminal_tasks(db_session: Session, state: TaskStatus) -> None:
    task = enqueue(db_session)
    task.status = state
    task.started_at = utc_now()
    task.execution_id = uuid.uuid4()
    task.lease_expires_at = utc_now() + timedelta(minutes=5)
    db_session.commit()
    assert consume(db_session) is None
    assert db_session.scalar(select(func.count()).select_from(SourceChunk)) == 0


def test_attempt_limit_requires_manual_retry(db_session: Session) -> None:
    task = enqueue(db_session)
    task.status = TaskStatus.RUNNING
    task.attempt_count = 3
    task.execution_id = uuid.uuid4()
    task.lease_expires_at = utc_now() - timedelta(seconds=1)
    db_session.commit()
    result = consume(db_session)
    assert result.status == TaskStatus.FAILED
    assert result.error["code"] == "TASK_ATTEMPTS_EXHAUSTED"
    assert result.execution_id is None and result.lease_expires_at is None
    assert db_session.get(SourceDocument, task.source_id).status == SourceStatus.FAILED
    assert consume(db_session) is None
    retried = parsing.run_task(db_session, user_id=task.user_id, task_id=task.id)
    assert retried.status == TaskStatus.SUCCEEDED
    assert retried.attempt_count == 4


def test_worker_failure_is_sanitized_and_not_retried(db_session: Session, monkeypatch, caplog) -> None:
    task = enqueue(db_session)

    def fail(*args, **kwargs):
        raise ValueError("private document text")

    monkeypatch.setattr(parsing, "parse_markdown", fail)
    with caplog.at_level(logging.WARNING):
        result = consume(db_session)
    assert result.status == TaskStatus.FAILED
    assert result.error["code"] == "SOURCE_PARSE_FAILED"
    assert "private document text" not in str(result.error) + caplog.text
    assert consume(db_session) is None


@pytest.mark.parametrize("excluded", ["other_user", "archived", "type", "source_type", "project_mismatch", "source_user_mismatch"])
def test_worker_preserves_boundaries(db_session: Session, excluded: str) -> None:
    task = enqueue(db_session)
    if excluded == "other_user":
        other_user = uuid.uuid4()
        db_session.get(Project, task.project_id).user_id = other_user
        db_session.get(SourceDocument, task.source_id).user_id = other_user
        task.user_id = other_user
    elif excluded == "archived":
        db_session.get(Project, task.project_id).archived_at = utc_now()
    elif excluded == "type":
        task.type = "future_extraction"
    elif excluded == "source_type":
        db_session.get(SourceDocument, task.source_id).source_type = "future_code"
    elif excluded == "project_mismatch":
        other = Project(user_id=task.user_id, name="Other")
        db_session.add(other)
        db_session.flush()
        db_session.get(SourceDocument, task.source_id).project_id = other.id
    else:
        db_session.get(SourceDocument, task.source_id).user_id = uuid.uuid4()
    db_session.commit()
    assert consume(db_session) is None
    assert task.status == TaskStatus.QUEUED


@pytest.mark.parametrize("late_failure", [False, True])
def test_replaced_execution_cannot_overwrite_new_result(tmp_path, monkeypatch, late_failure: bool) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'worker.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    original = parsing.parse_markdown
    with factory() as first:
        task = enqueue(first)
        source_id, task_id = task.source_id, task.id

        def replace_execution(content: str, *, source_id: uuid.UUID):
            with factory() as second:
                running = second.get(ProcessingTask, task_id)
                old_token = running.execution_id
                assert old_token is not None and running.attempt_count == 1
                assert consume(second) is None  # Lease is still live.
                second.execute(update(ProcessingTask).where(ProcessingTask.id == task_id)
                               .values(lease_expires_at=utc_now() - timedelta(seconds=1)))
                second.commit()
                monkeypatch.setattr(parsing, "parse_markdown", original)
                assert consume(second).status == TaskStatus.SUCCEEDED
            if late_failure:
                raise ValueError("old process failed late")
            return original("STALE RESULT", source_id=source_id)

        monkeypatch.setattr(parsing, "parse_markdown", replace_execution)
        result = parsing.run_task(first, user_id=task.user_id, task_id=task_id)
        assert result.status == TaskStatus.SUCCEEDED
        assert result.attempt_count == 2
        actual = list(first.scalars(select(SourceChunk).order_by(SourceChunk.position)))
        expected = original("# Evidence\n\nKeep source locations.\n", source_id=source_id)
        assert [chunk.id for chunk in actual] == [chunk.id for chunk in expected]
        assert [chunk.content for chunk in actual] == [chunk.content for chunk in expected]
        assert first.get(SourceDocument, source_id).status == SourceStatus.READY
    engine.dispose()


def test_once_drains_at_most_one_task(db_session: Session) -> None:
    first = enqueue(db_session)
    second = enqueue(db_session)

    class BorrowSession:
        def __enter__(self):
            return db_session

        def __exit__(self, *args):
            pass

    assert worker.serve(settings=Settings(), user_id=DEVELOPMENT_USER_ID, once=True,
                        stop=threading.Event(), session_factory=BorrowSession) == 0
    assert first.status == TaskStatus.SUCCEEDED
    assert second.status == TaskStatus.QUEUED


def test_worker_shutdown_and_failure_exit_codes(db_session: Session, monkeypatch) -> None:
    stop = threading.Event()
    stop.set()
    assert worker.serve(settings=Settings(), user_id=DEVELOPMENT_USER_ID,
                        once=False, stop=stop) == 0

    def unavailable():
        raise RuntimeError("connection details must remain private")

    assert worker.serve(settings=Settings(), user_id=DEVELOPMENT_USER_ID, once=True,
                        stop=threading.Event(), session_factory=unavailable) == 1


@pytest.mark.parametrize("infrastructure_error", [False, True])
def test_idle_and_error_iterations_wait_and_allow_shutdown(db_session: Session, monkeypatch, infrastructure_error: bool) -> None:
    class StopOnWait(threading.Event):
        waited: float | None = None

        def wait(self, timeout=None):
            self.waited = timeout
            self.set()
            return True

    stop = StopOnWait()

    def session_factory():
        if infrastructure_error:
            raise RuntimeError("database unavailable")
        return nullcontext(db_session)

    monkeypatch.setattr(worker, "process_next", lambda *args, **kwargs: None)
    assert worker.serve(settings=Settings(), user_id=DEVELOPMENT_USER_ID, once=False,
                        stop=stop, session_factory=session_factory) == 0
    assert stop.waited == 2


@pytest.mark.parametrize("values", [
    {"task_lease_seconds": 0}, {"task_max_attempts": 0},
    {"worker_poll_interval_seconds": 0}, {"worker_poll_interval_seconds": 61},
])
def test_worker_configuration_rejects_invalid_limits(values: dict) -> None:
    with pytest.raises(ValidationError):
        Settings(**values)


def test_worker_cli_processes_persisted_tasks_and_reports_failure(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    url = f"sqlite+pysqlite:///{(tmp_path / 'cli.db').as_posix()}"
    env = {**os.environ, "DATABASE_URL": url, "APP_ENV": "testing"}
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=root, env=env, capture_output=True, text=True, timeout=20,
    )
    assert migration.returncode == 0, migration.stderr
    engine = create_engine(url)
    with Session(engine, expire_on_commit=False) as db:
        task = enqueue(db)
        task_id = task.id
    result = subprocess.run(
        [sys.executable, "-m", "app.worker", "--once"],
        cwd=root, env=env, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    with Session(engine) as db:
        assert db.get(ProcessingTask, task_id).status == TaskStatus.SUCCEEDED
        assert db.scalar(select(func.count()).select_from(SourceChunk)) == 2
        failed = enqueue(db)
        failed_id = failed.id
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TRIGGER reject_chunks BEFORE INSERT ON source_chunks "
            "BEGIN SELECT RAISE(ABORT, 'private database details'); END"
        ))
    result = subprocess.run(
        [sys.executable, "-m", "app.worker", "--once"],
        cwd=root, env=env, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 1
    assert "private database details" not in result.stdout + result.stderr
    with Session(engine) as db:
        assert db.get(ProcessingTask, failed_id).status == TaskStatus.FAILED
        assert db.scalar(select(func.count()).select_from(SourceChunk)) == 2
    engine.dispose()
