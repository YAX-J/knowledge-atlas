"""Independent-session races, enabled only inside the disposable native runner."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
import os
import re
import threading
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.identity import DEVELOPMENT_USER_ID
from app.db.session import get_db
from app.main import app
from app.models.domain import ProcessingTask, SourceChunk, SourceDocument, TaskStatus, utc_now
from app.models.evolution import KnowledgeChange
from app.models.graph import KnowledgeEntity
from app.services import parsing
from tests.test_evolution import pair, proposal, propose, resolve, reviewed_decision
from tests.test_knowledge import configured
from tests.test_parsing import upload
from tests.test_sources import create_project
from tests.test_worker import enqueue

pytestmark = pytest.mark.skipif(not os.environ.get("KA_ACCEPTANCE_SCHEMA"), reason="requires disposable native PostgreSQL runner")


@contextmanager
def independent_client():
    schema = os.environ["KA_ACCEPTANCE_SCHEMA"]
    assert re.fullmatch(r"ka_acceptance_[0-9a-f]{32}", schema)
    url = make_url(os.environ["DATABASE_URL"])
    assert url.query.get("options") == f"-csearch_path={schema},public"
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.scalar(text("select current_schema()")) == schema
        assert connection.scalar(text("SELECT count(*) FROM information_schema.tables WHERE table_schema=:schema "
                                      "AND table_name IN ('projects','knowledge_entities','source_documents','knowledge_changes')"),
                                 {"schema": schema}) == 4
    def database_session():
        with Session(engine, expire_on_commit=False) as db:
            yield db
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = database_session
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        if previous is None: app.dependency_overrides.pop(get_db, None)
        else: app.dependency_overrides[get_db] = previous
        engine.dispose()


def race(function, values):
    barrier = threading.Barrier(len(values), timeout=15)
    def run(value):
        barrier.wait()
        return function(value)
    with ThreadPoolExecutor(max_workers=len(values)) as pool:
        return list(pool.map(run, values))


def test_native_rebuild_job_serializes_duplicate_requests_and_persists_status(monkeypatch):
    from app.services import embedding_jobs
    entered, release = threading.Event(), threading.Event()
    calls = []
    def rebuild(db, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(10)
        kwargs['checkpoint'](False)
        return dict(model='stub', dimensions=1024, eligible_count=0, updated_count=0, reused_count=0)
    monkeypatch.setattr(embedding_jobs, 'rebuild_project_embeddings', rebuild)
    with independent_client() as (client, engine):
        project = create_project(client)
        url = f'/api/v1/projects/{project}/embeddings'
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(client.post, url + '/rebuild')
            try:
                assert entered.wait(10)
                assert client.post(url + '/rebuild').status_code == 409
                assert client.get(url + '/rebuild-status').json()['status'] == 'running'
            finally:
                release.set()
            assert future.result(timeout=10).status_code == 200
        assert len(calls) == 1
        assert client.get(url + '/rebuild-status').json()['status'] == 'succeeded'


def test_native_retirement_serializes_competing_and_repeated_requests(configured, monkeypatch):
    from tests.test_retirement import prepared, request
    from app.models.retirement import KnowledgeRetirement
    with independent_client() as (client, engine):
        project, records = prepared(client, monkeypatch)
        selected = next(item for item in records if item['kind'] == 'entity')
        url = f'/api/v1/projects/{project}/knowledge-retirements'
        payloads = [request(selected), request(selected)]
        responses = race(lambda payload:client.post(url,json=payload),payloads)
        assert sorted(item.status_code for item in responses) == [200,409]
        winner = next(payload for payload,response in zip(payloads,responses) if response.status_code == 200)
        repeated = race(lambda _:client.post(url,json=winner),range(3))
        assert all(item.status_code == 200 and item.json() == repeated[0].json() for item in repeated)
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(KnowledgeRetirement).where(
                KnowledgeRetirement.project_id == uuid.UUID(project))) == 1


def test_native_concurrent_upload_and_replacement_are_idempotent(configured, monkeypatch):
    with independent_client() as (client, engine):
        project = create_project(client)
        imports = race(lambda _: upload(client, project), range(4))
        assert len({item["source_id"] for item in imports}) == len({item["task_id"] for item in imports}) == 1
        project, old, new = pair(client, monkeypatch)
        data = proposal(old, new)
        changes = race(lambda _: propose(client, project, data), range(4))
        assert len({item["id"] for item in changes}) == 1
        resolved = race(lambda item: resolve(client, project, item), changes)
        assert all(item.status_code == 200 for item in resolved)
        assert all(item.json() == resolved[0].json() for item in resolved)
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(KnowledgeChange).where(KnowledgeChange.project_id == uuid.UUID(project))) == 1


def test_native_competing_successors_have_one_winner(configured, monkeypatch):
    with independent_client() as (client, engine):
        project, old, new = pair(client, monkeypatch)
        third = reviewed_decision(client, monkeypatch, project, 3)
        changes = [propose(client, project, proposal(old, successor)) for successor in (new, third)]
        responses = race(lambda change: resolve(client, project, change), changes)
        assert sorted(item.status_code for item in responses) == [200, 409]
        with Session(engine) as db:
            rows = list(db.scalars(select(KnowledgeChange).where(KnowledgeChange.project_id == uuid.UUID(project))))
            assert sorted(item.review_status for item in rows) == ["confirmed", "pending"]
            assert db.get(KnowledgeEntity, uuid.UUID(old["entity"]["id"])).status == "superseded"


def test_native_worker_recovery_fences_the_abandoned_execution():
    with independent_client() as (_, engine):
        with Session(engine, expire_on_commit=False) as db:
            task = enqueue(db)
            task.status = TaskStatus.RUNNING
            abandoned = uuid.uuid4()
            task.execution_id = abandoned
            task.attempt_count = 1
            task.lease_expires_at = utc_now() - timedelta(seconds=1)
            db.commit()
            task_id = task.id
        def recover(_):
            with Session(engine, expire_on_commit=False) as db:
                try:
                    result = parsing.run_task(db, user_id=DEVELOPMENT_USER_ID, task_id=task_id, recover_expired=True)
                    return result.status
                except Exception as exc:
                    from app.core.errors import AppError
                    assert isinstance(exc, AppError) and exc.code == "TASK_NOT_RUNNABLE"
                    return "contended"
        statuses = race(recover, range(4))
        assert TaskStatus.SUCCEEDED in statuses
        with Session(engine) as db:
            task = db.get(ProcessingTask, task_id)
            assert task.status == TaskStatus.SUCCEEDED and task.attempt_count == 2
            assert db.scalar(select(func.count()).select_from(SourceChunk).where(SourceChunk.source_id == task.source_id)) == 2
            assert parsing._finish_task(db, task=task, execution_id=abandoned, chunks=[]) is False
            assert db.get(ProcessingTask, task_id).status == TaskStatus.SUCCEEDED
            assert db.scalar(select(func.count()).select_from(SourceChunk).where(SourceChunk.source_id == task.source_id)) == 2
