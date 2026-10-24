from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import uuid

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.identity import DEVELOPMENT_USER_ID
from app.db.base import Base
from app.models.domain import CandidateKnowledge, Project, ReviewEvent, SourceDocument
from app.models.evolution import KnowledgeChange
from app.models.graph import KnowledgeEntity, KnowledgeEvidence
from app.services import graph, knowledge
from scripts.prepare_evaluation import PreparationError, load_fixture, prepare_project
from scripts import prepare_evaluation as preparation
from scripts.run_evaluation import map_project_sources


DATASET = Path(__file__).resolve().parents[2] / "evaluation"


@pytest.fixture
def evaluation_engine():
    engine = create_engine("sqlite+pysqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def prepare(engine, **kwargs):
    return prepare_project(engine=engine, dataset_root=DATASET,
                           project_id=kwargs.pop("project_id", uuid.uuid4()),
                           settings=Settings(_env_file=None), accept_curated_fixture=True, **kwargs)


def test_curated_fixture_matches_corpus_and_has_nonzero_graph_relations():
    fixture, summary, fingerprint = load_fixture(DATASET)
    assert len(fixture.sources) == summary["source_count"] == 30
    assert sum(len(item.relations) for item in fixture.sources) >= 10
    assert len(fixture.changes) == 1 and len(fingerprint) == 64
    assert summary["version"] == "1.0.1"


def test_initialization_replays_reviews_and_time_boundaries(evaluation_engine, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Preparation cannot call a provider")

    monkeypatch.setattr("app.services.deepseek.extract_candidates", forbidden)
    monkeypatch.setattr("app.services.deepseek.answer_question", forbidden)
    monkeypatch.setattr("app.services.embeddings.embed_texts", forbidden)
    original_clock = graph.utc_now
    result = prepare(evaluation_engine)
    assert graph.utc_now is original_clock
    assert result["provider_call_count"] == 0
    counts = result["counts"]
    assert counts["sources"] == 30 and counts["tasks"] == 60
    assert counts["entities"] > 30 and counts["relationships"] >= 10
    assert counts["candidates"] == counts["reviews"] == counts["entities"] + counts["relationships"]
    project_id = uuid.UUID(result["project_id"])
    with Session(evaluation_engine) as db:
        assert len(map_project_sources(db, dataset_root=DATASET, corpus_root_name="corpus",
                                       project_id=project_id, user_id=DEVELOPMENT_USER_ID)) == 30
        assert db.scalar(select(func.count()).select_from(KnowledgeEvidence)) == counts["evidence"]
        assert db.scalar(select(KnowledgeChange.review_status)) == "confirmed"
        before = datetime(2026, 6, 14, 23, 59, 59, tzinfo=timezone.utc)
        boundary = datetime(2026, 6, 15, tzinfo=timezone.utc)
        for at, expected, excluded in ((before, "2025 存储决策", "2026 存储决策"),
                                      (boundary, "2026 存储决策", "2025 存储决策")):
            view = graph.get_graph(db, user_id=DEVELOPMENT_USER_ID, project_id=project_id,
                                   center_id=None, depth=1, types=[], valid_at=at, limit=100)
            names = {node.name for node in view.nodes}
            assert expected in names and excluded not in names
        assert all(record.review_status.value == "confirmed" for record in db.scalars(select(CandidateKnowledge)))
        assert db.scalar(select(func.count()).select_from(ReviewEvent)) == counts["reviews"]


def test_existing_project_refused_without_modifying_it(evaluation_engine):
    project_id = uuid.uuid4()
    with Session(evaluation_engine) as db:
        db.add(Project(id=project_id, user_id=DEVELOPMENT_USER_ID, name="User project", description="keep"))
        db.commit()
    with pytest.raises(PreparationError, match="already exists"):
        prepare(evaluation_engine, project_id=project_id)
    with Session(evaluation_engine) as db:
        assert db.get(Project, project_id).description == "keep"
        assert db.scalar(select(func.count()).select_from(SourceDocument)) == 0


def test_service_failure_rolls_back_entire_new_project(evaluation_engine, monkeypatch):
    project_id = uuid.uuid4()
    original = knowledge.resolve_review
    calls = 0

    def fail_late(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 5:
            raise PreparationError("injected failure after service commits")
        return original(*args, **kwargs)

    original_clock = graph.utc_now
    monkeypatch.setattr(knowledge, "resolve_review", fail_late)
    with pytest.raises(PreparationError, match="injected failure"):
        prepare(evaluation_engine, project_id=project_id)
    assert graph.utc_now is original_clock
    with Session(evaluation_engine) as db:
        for model in (Project, SourceDocument, CandidateKnowledge, ReviewEvent, KnowledgeEntity, KnowledgeEvidence):
            assert db.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("accepted,environment", [(False, "development"), (True, "production")])
def test_explicit_acceptance_and_environment_guards(evaluation_engine, accepted, environment):
    with pytest.raises(PreparationError):
        prepare_project(engine=evaluation_engine, dataset_root=DATASET, project_id=uuid.uuid4(),
                        settings=Settings(_env_file=None, app_env=environment), accept_curated_fixture=accepted)


@pytest.mark.parametrize("mutation,error", [
    (lambda data: data.update(dataset_fingerprint_sha256="0" * 64), "fingerprint"),
    (lambda data: data["sources"].pop(), "every corpus source"),
    (lambda data: data["sources"][0]["entities"][0].update(lines=[999]), "evidence lines"),
    (lambda data: data["sources"][1].update(available_at="2026-07-01T00:00:00Z"), "historical time"),
    (lambda data: data["sources"][2]["relations"][0].update(target="storage-old"), "same source"),
    (lambda data: data["changes"][0].update(effective_at="2025-01-01T00:00:00Z"), "both source"),
])
def test_invalid_fixture_rejected_before_database_write(tmp_path, mutation, error):
    dataset = tmp_path / "dataset"
    shutil.copytree(DATASET, dataset)
    path = dataset / "reviewed_graph.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    mutation(value)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(PreparationError, match=error):
        load_fixture(dataset)


def test_preparation_is_repeatable_with_identical_fixture(evaluation_engine):
    first = prepare(evaluation_engine)
    second = prepare(evaluation_engine)
    assert first["project_id"] != second["project_id"]
    assert first["fixture_fingerprint_sha256"] == second["fixture_fingerprint_sha256"]
    assert first["counts"] == second["counts"]
    assert first["snapshot"] == second["snapshot"]


def test_cli_validate_only_needs_neither_output_nor_database(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["prepare_evaluation", "--dataset", str(DATASET), "--validate-only"])
    monkeypatch.setattr(preparation, "configured_engine", None)
    assert preparation.main() == 0
    assert json.loads(capsys.readouterr().out)["dataset"]["version"] == "1.0.1"


def test_cli_refuses_existing_output_before_database_access(tmp_path, monkeypatch):
    marker = tmp_path / "preparation.json"
    marker.write_text("keep", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["prepare_evaluation", "--dataset", str(DATASET),
                                    "--output-dir", str(tmp_path), "--accept-curated-fixture"])
    monkeypatch.setattr(preparation, "configured_engine", None)
    assert preparation.main() == 2
    assert marker.read_text() == "keep"


@pytest.mark.skipif(not os.environ.get("KA_ACCEPTANCE_SCHEMA"), reason="Requires isolated native acceptance schema")
def test_native_evaluation_preparation(db_session):
    result = prepare(db_session.get_bind().engine)
    assert result["counts"]["sources"] == 30
    assert result["counts"]["changes"] == 1
    with Session(db_session.get_bind().engine) as db:
        project_id = uuid.UUID(result["project_id"])
        old_id = uuid.UUID(result["knowledge_ids"]["storage-old"])
        new_id = uuid.UUID(result["knowledge_ids"]["storage-new"])
        assert db.get(KnowledgeEntity, old_id).valid_to == db.get(KnowledgeEntity, new_id).valid_from
        assert len(map_project_sources(db, dataset_root=DATASET, corpus_root_name="corpus",
                                       project_id=project_id, user_id=DEVELOPMENT_USER_ID)) == 30
