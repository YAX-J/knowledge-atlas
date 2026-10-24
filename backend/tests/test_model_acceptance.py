import csv
import json
from pathlib import Path

from pydantic import SecretStr
import pytest

from app.core.config import Settings
from app.schemas.knowledge import ExtractionDraft
from app.schemas.questions import AnswerDraft
from scripts.evaluate_dataset import read_jsonl, validate_dataset
from scripts.import_grades import import_grades
from scripts import model_acceptance as acceptance

ROOT = Path(__file__).resolve().parents[2] / "evaluation"


def test_acceptance_and_empty_blind_grades_keep_human_coverage_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance, "benchmark", lambda *_args, **_kwargs: ([], {"mock": True}))

    def answer(_settings, _question, evidence):
        return AnswerDraft(supported=True, answer="Evidence based answer", confidence=.8,
                           citation_ids=[evidence[0]["id"]], missing_information=[])

    monkeypatch.setattr(acceptance.deepseek, "answer_question", answer)
    monkeypatch.setattr(acceptance.deepseek, "extract_candidates", lambda *_: ExtractionDraft(entities=[], relations=[]))
    output = tmp_path / "acceptance"
    result = acceptance.run_acceptance(
        dataset=ROOT, retrieval=ROOT / "results" / "2026-10-24-v101" / "retrieval", output=output,
        settings=Settings(_env_file=None, deepseek_api_key=SecretStr("test-key")), allow_model_calls=True)
    assert result["status"] == "succeeded" and result["blind_review_items"] == 120
    with (output / "blind-review.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 120 and all(not row["answer_correct"] for row in rows)
    assert "mode" not in rows[0]
    graded = import_grades(dataset=ROOT, acceptance=output, review_csv=output / "blind-review.csv", output=tmp_path / "graded")
    assert graded["reviewed_rows"] == 0
    assert all(item["answers"]["manual_grade_coverage"] == 0 for item in graded["metrics"].values())
    rows[0]["answer_correct"] = "true"
    invalid = tmp_path / "invalid.csv"
    with invalid.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="pseudonym"):
        import_grades(dataset=ROOT, acceptance=output, review_csv=invalid, output=tmp_path / "bad")


def test_acceptance_requires_explicit_authorization(tmp_path):
    with pytest.raises(ValueError, match="allow-model-calls"):
        acceptance.run_acceptance(dataset=ROOT, retrieval=tmp_path, output=tmp_path / "run",
                                   settings=Settings(_env_file=None), allow_model_calls=False)
    assert not (tmp_path / "run").exists()


def test_frozen_answer_replay_rejects_provider_forged_citation(monkeypatch):
    _, cases, _ = validate_dataset(ROOT)
    frozen = read_jsonl(ROOT / "results" / "2026-10-24-v101" / "retrieval" / "vector.jsonl")
    monkeypatch.setattr(acceptance.deepseek, "answer_question", lambda *_: AnswerDraft(
        supported=True, answer="bad", confidence=.5, citation_ids=["00000000-0000-0000-0000-000000000001"], missing_information=[]))
    with pytest.raises(ValueError, match="outside"):
        acceptance.answer_replay(Settings(_env_file=None), root=ROOT, cases=cases, frozen=frozen)
