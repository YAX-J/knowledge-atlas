import json
import math
from pathlib import Path
import uuid

from pydantic import SecretStr
import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.models.graph import KnowledgeEntity
from app.services.embeddings import EmbeddingError
from scripts.prepare_evaluation import prepare_project
from scripts.run_baselines import run_baselines
from scripts.run_evaluation import EvaluationRunError


DATASET = Path(__file__).resolve().parents[2] / "evaluation"


def configuration():
    return Settings(_env_file=None, embedding_api_key=SecretStr("test-embedding-key"),
                    embedding_base_url="https://embedding.example.test/v1", embedding_model="mock-vector")


def prepared_report(engine, tmp_path):
    result = prepare_project(engine=engine, dataset_root=DATASET, project_id=uuid.uuid4(),
                             settings=Settings(_env_file=None), accept_curated_fixture=True)
    path = tmp_path / "preparation.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    return path, result


def test_three_baselines_complete_on_one_snapshot_without_answers(db_session, tmp_path, monkeypatch):
    path, prepared = prepared_report(db_session.get_bind(), tmp_path)
    inputs = []

    def embed(_settings, texts):
        inputs.extend(texts)
        return [[1.0, *([0.0] * 1023)] for _ in texts]

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Answer provider must not run")

    monkeypatch.setattr("app.services.embeddings.embed_texts", embed)
    monkeypatch.setattr("app.services.deepseek.answer_question", forbidden)
    result = run_baselines(dataset_root=DATASET, preparation_report=path, output_dir=tmp_path / "baselines",
                           engine=db_session.get_bind(), settings=configuration(), allow_embedding_calls=True)
    assert result["status"] == "succeeded" and result["answer_calls"] == 0
    assert result["embedding_calls"]["successful"] == 80 + math.ceil(prepared["counts"]["entities"] / 10)
    assert result["embedding_calls"]["failed"] == 0
    assert result["project_snapshot"]["knowledge_sha256"] == prepared["snapshot"]["knowledge_sha256"]
    assert result["project_snapshot"]["indexed_entity_count"] == prepared["counts"]["entities"]
    assert len(result["comparison"]) == 3
    assert all(row["answer_evaluation_coverage"] == 0 for row in result["comparison"])
    assert result["comparison"][2]["positive_graph_hits"] > 0
    assert len(inputs) == 80 + prepared["counts"]["entities"]
    assert (tmp_path / "baselines" / "comparison.csv").is_file()


def test_no_authorization_refuses_before_files_or_database(tmp_path):
    with pytest.raises(EvaluationRunError, match="allow-embedding-calls"):
        run_baselines(dataset_root=DATASET, preparation_report=tmp_path / "missing.json",
                      output_dir=tmp_path / "run", engine=None,
                      settings=configuration(), allow_embedding_calls=False)
    assert not (tmp_path / "run").exists()


def test_provider_failure_records_attempt_and_preserves_project(db_session, tmp_path, monkeypatch):
    path, prepared = prepared_report(db_session.get_bind(), tmp_path)

    def fail(*_args):
        raise EmbeddingError("EMBEDDING_PROVIDER_FAILED", "sanitized error")

    monkeypatch.setattr("app.services.embeddings.embed_texts", fail)
    with pytest.raises(Exception):
        run_baselines(dataset_root=DATASET, preparation_report=path, output_dir=tmp_path / "run",
                      engine=db_session.get_bind(), settings=configuration(), allow_embedding_calls=True)
    report = json.loads((tmp_path / "run" / "baselines.json").read_text())
    assert report["status"] == "failed"
    assert report["embedding_calls"] == {"attempted": 1, "successful": 0, "failed": 1,
                                         "texts": 10, "input_characters": report["embedding_calls"]["input_characters"]}
    assert report["error_code"] == "EMBEDDING_PROVIDER_FAILED"
    assert db_session.scalar(select(KnowledgeEntity).limit(1)) is not None
    assert report["project_id"] == prepared["project_id"]


def test_modified_project_refused_before_output_or_provider(db_session, tmp_path):
    path, _ = prepared_report(db_session.get_bind(), tmp_path)
    entity = db_session.scalar(select(KnowledgeEntity).limit(1))
    entity.summary = "modified after preparation"
    db_session.commit()
    with pytest.raises(EvaluationRunError, match="knowledge changed"):
        run_baselines(dataset_root=DATASET, preparation_report=path, output_dir=tmp_path / "run",
                      engine=db_session.get_bind(), settings=configuration(), allow_embedding_calls=True)
    assert not (tmp_path / "run").exists()
