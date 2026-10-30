import uuid
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.schemas.questions import AnswerDraft, ClaimAnswerDraft
from sqlalchemy.orm import sessionmaker
from scripts.prepare_evaluation import prepare_project
from scripts import run_evaluation as runner
from scripts.run_evaluation import EvaluationRunError, answer_from_result, build_prediction


def evidence(identifier, source_id, quote="gold quote"):
    return SimpleNamespace(
        id=identifier,
        source_id=source_id,
        title="source.md",
        start_line=5,
        end_line=5,
        quote=quote,
    )


def result_with(evidence_items, *, indexed_count=None, eligible_count=None):
    return SimpleNamespace(
        items=[SimpleNamespace(
            entity=SimpleNamespace(name="Gold entity"),
            evidence=evidence_items,
        )],
        indexed_count=indexed_count,
        eligible_count=eligible_count,
    )


def test_build_prediction_keeps_retrieval_order_without_answer_calls():
    source_id = uuid.uuid4()
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    result = result_with([
        evidence(first_id, source_id, "first"),
        evidence(second_id, source_id, "second"),
        evidence(first_id, source_id, "first"),
    ])
    calls = []

    def search(*args, **kwargs):
        calls.append((args, kwargs))
        return result

    prediction, answer_called = build_prediction(
        db=SimpleNamespace(),
        settings=Settings(_env_file=None),
        user_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        case={"id": "direct-001", "question": "question", "valid_at": None},
        mode="keyword",
        top_k=5,
        with_answers=False,
        source_paths={source_id: "corpus/docs/source.md"},
        search_fn=search,
    )

    assert [item["quote"] for item in prediction["retrieved_evidence"]] == ["first", "second"]
    assert prediction["answer"] is prediction["supported"] is None
    assert prediction["citations"] == [] and not answer_called
    assert calls[0][1]["mode"] == "keyword" and calls[0][1]["top_k"] == 5


@pytest.mark.parametrize('claim_format', [False, True])
def test_answer_generation_accepts_only_retrieved_citations(claim_format):
    source_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    result = result_with([evidence(evidence_id, source_id)])

    def answer(_settings, question, payload):
        assert question == "question"
        assert payload[0]["id"] == str(evidence_id)
        if claim_format:
            return ClaimAnswerDraft(supported=True,confidence=.9,
                claims=[dict(text='grounded answer',status='supported',citation_ids=[evidence_id])],missing_information=[])
        return AnswerDraft(
            supported=True,
            answer="grounded answer",
            confidence=.9,
            citation_ids=[evidence_id],
            missing_information=[],
        )

    generated, supported, citations, called = answer_from_result(
        settings=Settings(_env_file=None),
        question="question",
        result=result,
        source_paths={source_id: "corpus/docs/source.md"},
        answer_fn=answer,
    )

    assert generated == "grounded answer" and supported and called
    assert citations == [{
        "source": "corpus/docs/source.md",
        "start_line": 5,
        "end_line": 5,
        "quote": "gold quote",
    }]


def test_answer_generation_rejects_unknown_citation():
    source_id = uuid.uuid4()
    result = result_with([evidence(uuid.uuid4(), source_id)])

    def answer(*_):
        return AnswerDraft(
            supported=True,
            answer="bad citation",
            confidence=.5,
            citation_ids=[uuid.uuid4()],
            missing_information=[],
        )

    with pytest.raises(EvaluationRunError, match="outside this retrieval result"):
        answer_from_result(
            settings=Settings(_env_file=None),
            question="question",
            result=result,
            source_paths={source_id: "corpus/docs/source.md"},
            answer_fn=answer,
        )


@pytest.mark.parametrize('mode', ['vector', 'hybrid', 'rrf'])
def test_vector_prediction_requires_complete_index(mode):
    source_id = uuid.uuid4()
    result = result_with([evidence(uuid.uuid4(), source_id)], indexed_count=1, eligible_count=2)

    with pytest.raises(EvaluationRunError, match="incomplete"):
        build_prediction(
            db=SimpleNamespace(),
            settings=Settings(_env_file=None),
            user_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            case={"id": "direct-001", "question": "question", "valid_at": None},
            mode=mode,
            top_k=5,
            with_answers=False,
            source_paths={source_id: "corpus/docs/source.md"},
            search_fn=lambda *_args, **_kwargs: result,
        )


@pytest.mark.parametrize('mode', ['keyword', 'bm25'])
def test_prepared_project_runs_all_keyword_cases_without_providers(db_session, tmp_path, monkeypatch, mode):
    dataset = Path(__file__).resolve().parents[2] / "evaluation"
    engine = db_session.get_bind()
    project_id = uuid.uuid4()
    prepared = prepare_project(engine=engine, dataset_root=dataset, project_id=project_id,
                               settings=Settings(_env_file=None), accept_curated_fixture=True)
    monkeypatch.setattr(runner, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    result = runner.run_evaluation(dataset_root=dataset, project_id=project_id, output_dir=tmp_path / "run",
                                   modes=[mode], top_k=5, with_answers=False,
                                   allow_embedding_calls=False, settings=Settings(_env_file=None))
    assert result["status"] == "succeeded"
    assert result["outputs"][mode]["case_count"] == 40
    assert result["successful_provider_call_counts"] == {"embedding": 0, "answer": 0}
    assert result["project_snapshot"] == prepared["snapshot"]
    predictions = (tmp_path / "run" / f"{mode}.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(predictions) == 40
    assert all(json.loads(item)["answer"] is None for item in predictions)


def test_runner_rejects_graph_drift_and_retains_partial_results(db_session, tmp_path, monkeypatch):
    dataset = Path(__file__).resolve().parents[2] / "evaluation"
    engine = db_session.get_bind()
    project_id = uuid.uuid4()
    prepare_project(engine=engine, dataset_root=dataset, project_id=project_id,
                    settings=Settings(_env_file=None), accept_curated_fixture=True)
    monkeypatch.setattr(runner, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    real_snapshot = runner.project_snapshot
    snapshots = 0

    def changed_snapshot(*args, **kwargs):
        nonlocal snapshots
        snapshots += 1
        value = real_snapshot(*args, **kwargs)
        if snapshots > 1:
            value["knowledge_sha256"] = "changed"
        return value

    monkeypatch.setattr(runner, "project_snapshot", changed_snapshot)
    output = tmp_path / "drift"
    with pytest.raises(EvaluationRunError, match="changed during"):
        runner.run_evaluation(dataset_root=dataset, project_id=project_id, output_dir=output,
                               modes=["keyword"], top_k=5, with_answers=False,
                               allow_embedding_calls=False, settings=Settings(_env_file=None))
    assert json.loads((output / "run.json").read_text())["status"] == "failed"
    assert (output / "keyword.partial.jsonl").is_file()
    assert not (output / "keyword.jsonl").exists()
