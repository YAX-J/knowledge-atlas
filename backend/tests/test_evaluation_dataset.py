from pathlib import Path

import pytest

from scripts.evaluate_dataset import DatasetError, score_predictions, validate_dataset


DATASET_ROOT = Path(__file__).resolve().parents[2] / "evaluation"


def test_frozen_evaluation_dataset_has_exact_evidence_and_expected_distribution():
    _, cases, summary = validate_dataset(DATASET_ROOT)

    assert summary["source_count"] == 30
    assert summary["case_count"] == 40
    assert summary["answerable_count"] == 36
    assert summary["category_counts"] == {
        "code_location": 6,
        "cross_document": 8,
        "direct_fact": 16,
        "temporal": 6,
        "unanswerable": 4,
    }
    assert len(summary["fingerprint_sha256"]) == 64
    assert all(case["gold_evidence"] for case in cases if case["answerable"])


def test_perfect_predictions_score_gold_citations_and_manual_metrics():
    _, cases, _ = validate_dataset(DATASET_ROOT)
    predictions = [{
        "id": case["id"],
        "retrieved_evidence": case["gold_evidence"],
        "citations": case["gold_evidence"],
        "answer": case["gold_answer"] + " " + " ".join(case["required_facts"]),
        "supported": case["answerable"],
        "latency_ms": 100,
        "answer_correct": True,
        "explainability_score": 5,
    } for case in cases]

    metrics = score_predictions(cases, predictions)

    assert metrics["retrieval"]["evidence_recall_at_1"] > 0
    assert metrics["retrieval"]["evidence_recall_at_5"] > metrics["retrieval"]["evidence_recall_at_1"]
    assert metrics["citations"] == {
        "precision": 1.0, "recall": 1.0, "f1": 1.0, "evaluation_coverage": 1.0,
    }
    assert metrics["answers"] == {
        "supported_or_refusal_accuracy": 1.0,
        "required_fact_coverage": 1.0,
        "automatic_evaluation_coverage": 1.0,
        "manual_answer_accuracy": 1.0,
        "manual_grade_coverage": 1.0,
        "cross_document_accuracy": 1.0,
        "historical_trace_accuracy": 1.0,
    }
    assert metrics["latency_ms"] == {"mean": 100.0, "p95": 100.0}
    assert metrics["explainability"] == {"mean_score_1_to_5": 5.0, "grade_coverage": 1.0}


def test_predictions_must_cover_every_case():
    _, cases, _ = validate_dataset(DATASET_ROOT)
    with pytest.raises(DatasetError, match="cover every case"):
        score_predictions(cases, [])


def test_prediction_contract_rejects_non_finite_latency():
    _, cases, _ = validate_dataset(DATASET_ROOT)
    predictions = [{
        "id": case["id"],
        "retrieved_evidence": [],
        "citations": [],
        "answer": "",
        "supported": False,
        "latency_ms": float("nan") if index == 0 else 0,
    } for index, case in enumerate(cases)]
    with pytest.raises(DatasetError, match="finite non-negative"):
        score_predictions(cases, predictions)


def test_retrieval_only_predictions_leave_answer_metrics_unscored():
    _, cases, _ = validate_dataset(DATASET_ROOT)
    predictions = [{
        "id": case["id"],
        "retrieved_evidence": case["gold_evidence"],
        "citations": [],
        "answer": None,
        "supported": None,
        "latency_ms": 25,
    } for case in cases]

    metrics = score_predictions(cases, predictions)

    assert metrics["retrieval"]["evidence_recall_at_5"] == 1.0
    assert metrics["citations"] == {
        "precision": None, "recall": None, "f1": None, "evaluation_coverage": 0.0,
    }
    assert metrics["answers"]["supported_or_refusal_accuracy"] is None
    assert metrics["answers"]["required_fact_coverage"] is None
    assert metrics["answers"]["automatic_evaluation_coverage"] == 0.0
