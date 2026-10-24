import copy
from pathlib import Path

import pytest

from app.core.config import Settings
from scripts.evaluate_calls import benchmark, CallDatasetError, score_calls, validate_calls

ROOT = Path(__file__).resolve().parents[2] / "evaluation" / "calls"


def test_frozen_calls_have_exact_evidence_and_all_languages():
    _, cases, summary = validate_calls(ROOT)
    assert summary["case_count"] == 50 and summary["source_count"] == 30
    assert len(summary["languages"]) == 10
    perfect = [{"id": case["id"], "candidate_present": True,
                "resolution": case["resolution"], "targets": case["targets"]} for case in cases]
    metrics = score_calls(cases, perfect)
    assert metrics["exact_decision_accuracy"] == metrics["target_f1"] == 1
    with pytest.raises(CallDatasetError):
        score_calls(cases, perfect[:-1])


def test_static_benchmark_is_complete_and_exposes_candidate_gaps():
    predictions, report = benchmark(ROOT, mode="static", settings=Settings(_env_file=None))
    assert len(predictions) == 50
    assert all(run["provider_calls"] == 0 for run in report["runs"])
    assert report["metrics"]["candidate_coverage"] < 1
    assert report["metrics"]["exact_decision_accuracy"] < 1
