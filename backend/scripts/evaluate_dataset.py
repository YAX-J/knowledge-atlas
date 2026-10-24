"""Validate and score the frozen Knowledge Atlas evaluation set.

This module intentionally performs no API, model, embedding, or database calls.
It validates gold evidence against the checked-in corpus and scores an exported
prediction JSONL file with deterministic metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


CATEGORIES = {
    "direct_fact",
    "cross_document",
    "code_location",
    "temporal",
    "unanswerable",
}
CASE_FIELDS = {
    "id",
    "category",
    "question",
    "answerable",
    "valid_at",
    "gold_answer",
    "required_facts",
    "gold_evidence",
    "expected_entities",
    "expected_relations",
}
EVIDENCE_FIELDS = {"source", "start_line", "end_line", "quote"}
RELATION_TYPES = {
    "BELONGS_TO",
    "CONTAINS",
    "DEPENDS_ON",
    "CALLS",
    "USES",
    "SOLVES",
    "CAUSED_BY",
    "AFFECTS",
    "DECIDED_IN",
    "CHOSEN_OVER",
    "CONSTRAINED_BY",
    "IMPLEMENTED_BY",
    "EVIDENCED_BY",
    "EXTRACTED_FROM",
    "LEARNED_FROM",
    "SUPERSEDES",
}
SUPPORTED_CORPUS_SUFFIXES = {
    ".md",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".cxx",
    ".cs",
}


class DatasetError(ValueError):
    """Raised when the dataset or predictions violate the frozen contract."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DatasetError(f"Expected a JSON object in {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DatasetError(f"Cannot read JSONL {path}: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetError(f"Invalid JSON in {path}:{line_number}: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise DatasetError(f"Expected an object in {path}:{line_number}")
        records.append(value)
    return records


def _non_empty_strings(value: Any, field: str, case_id: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise DatasetError(f"{case_id}.{field} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise DatasetError(f"{case_id}.{field} contains duplicates")
    return value


def _validate_evidence_shape(item: Any, case_id: str) -> dict[str, Any]:
    if not isinstance(item, dict) or set(item) != EVIDENCE_FIELDS:
        raise DatasetError(f"{case_id} evidence fields must be {sorted(EVIDENCE_FIELDS)}")
    source = item["source"]
    quote = item["quote"]
    start = item["start_line"]
    end = item["end_line"]
    if not isinstance(source, str) or not source.startswith("corpus/"):
        raise DatasetError(f"{case_id} evidence source must start with corpus/")
    if not isinstance(quote, str) or not quote:
        raise DatasetError(f"{case_id} evidence quote must be non-empty")
    if not isinstance(start, int) or isinstance(start, bool) or start < 1:
        raise DatasetError(f"{case_id} evidence start_line must be a positive integer")
    if not isinstance(end, int) or isinstance(end, bool) or end < start:
        raise DatasetError(f"{case_id} evidence end_line must be >= start_line")
    return item


def _evidence_key(item: dict[str, Any]) -> tuple[str, int, int, str]:
    return item["source"], item["start_line"], item["end_line"], item["quote"]


def _validate_case(case: dict[str, Any], dataset_root: Path) -> None:
    case_id = case.get("id", "<missing-id>")
    if set(case) != CASE_FIELDS:
        missing = sorted(CASE_FIELDS - set(case))
        extra = sorted(set(case) - CASE_FIELDS)
        raise DatasetError(f"{case_id} has missing fields {missing} and extra fields {extra}")
    if not isinstance(case_id, str) or not case_id:
        raise DatasetError("Case id must be a non-empty string")
    if case["category"] not in CATEGORIES:
        raise DatasetError(f"{case_id} has unknown category {case['category']!r}")
    if not isinstance(case["question"], str) or not 1 <= len(case["question"].strip()) <= 200:
        raise DatasetError(f"{case_id}.question must contain 1-200 characters")
    if not isinstance(case["answerable"], bool):
        raise DatasetError(f"{case_id}.answerable must be boolean")
    if not isinstance(case["gold_answer"], str) or not case["gold_answer"].strip():
        raise DatasetError(f"{case_id}.gold_answer must be non-empty")
    if case["valid_at"] is not None:
        if not isinstance(case["valid_at"], str):
            raise DatasetError(f"{case_id}.valid_at must be an ISO timestamp or null")
        try:
            parsed = datetime.fromisoformat(case["valid_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise DatasetError(f"{case_id}.valid_at is not a valid ISO timestamp") from exc
        if parsed.tzinfo is None:
            raise DatasetError(f"{case_id}.valid_at must include a timezone")

    facts = _non_empty_strings(case["required_facts"], "required_facts", case_id)
    _non_empty_strings(case["expected_entities"], "expected_entities", case_id)
    relations = _non_empty_strings(case["expected_relations"], "expected_relations", case_id)
    unknown_relations = sorted(set(relations) - RELATION_TYPES)
    if unknown_relations:
        raise DatasetError(f"{case_id} has unknown relation types {unknown_relations}")

    evidence_value = case["gold_evidence"]
    if not isinstance(evidence_value, list):
        raise DatasetError(f"{case_id}.gold_evidence must be a list")
    evidence = [_validate_evidence_shape(item, case_id) for item in evidence_value]
    keys = [_evidence_key(item) for item in evidence]
    if len(keys) != len(set(keys)):
        raise DatasetError(f"{case_id}.gold_evidence contains duplicates")
    if case["answerable"] and (not facts or not evidence):
        raise DatasetError(f"{case_id} is answerable and requires facts plus evidence")
    if any(fact.casefold() not in case["gold_answer"].casefold() for fact in facts):
        raise DatasetError(f"{case_id}.gold_answer must contain every required fact verbatim")
    if not case["answerable"] and (facts or evidence):
        raise DatasetError(f"{case_id} is unanswerable and must not contain facts or evidence")
    if case["category"] == "unanswerable" and case["answerable"]:
        raise DatasetError(f"{case_id} uses unanswerable category but answerable=true")
    if case["category"] != "unanswerable" and not case["answerable"]:
        raise DatasetError(f"{case_id} is answerable=false outside the unanswerable category")

    root = dataset_root.resolve()
    for item in evidence:
        source = (dataset_root / item["source"]).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise DatasetError(f"{case_id} evidence source does not exist inside the dataset: {item['source']}")
        lines = source.read_text(encoding="utf-8").splitlines()
        if item["end_line"] > len(lines):
            raise DatasetError(f"{case_id} evidence range exceeds {item['source']}")
        selected = "\n".join(lines[item["start_line"] - 1:item["end_line"]])
        if selected != item["quote"]:
            raise DatasetError(
                f"{case_id} quote does not exactly match {item['source']}:"
                f"{item['start_line']}-{item['end_line']}"
            )


def dataset_fingerprint(dataset_root: Path, manifest: dict[str, Any], cases: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
    for case in cases:
        digest.update(json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
    corpus_root = dataset_root / manifest["corpus_root"]
    for path in sorted(item for item in corpus_root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(dataset_root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def validate_dataset(dataset_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    dataset_root = dataset_root.resolve()
    manifest = _read_json(dataset_root / "manifest.json")
    required_manifest = {
        "dataset_id",
        "version",
        "language",
        "created_at",
        "source_count",
        "case_count",
        "category_counts",
        "corpus_root",
        "cases_file",
        "license",
    }
    if set(manifest) != required_manifest:
        raise DatasetError("manifest.json does not match the frozen manifest contract")
    cases = read_jsonl(dataset_root / manifest["cases_file"])
    ids = [case.get("id") for case in cases]
    if len(ids) != len(set(ids)):
        raise DatasetError("Case ids must be unique")
    for case in cases:
        _validate_case(case, dataset_root)

    corpus_root = dataset_root / manifest["corpus_root"]
    sources = sorted(
        path for path in corpus_root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_CORPUS_SUFFIXES
    )
    category_counts = dict(sorted(Counter(case["category"] for case in cases).items()))
    expected_categories = dict(sorted(manifest["category_counts"].items()))
    if len(sources) != manifest["source_count"]:
        raise DatasetError(f"Expected {manifest['source_count']} corpus sources, found {len(sources)}")
    if len(cases) != manifest["case_count"]:
        raise DatasetError(f"Expected {manifest['case_count']} cases, found {len(cases)}")
    if category_counts != expected_categories:
        raise DatasetError(f"Category counts {category_counts} do not match manifest {expected_categories}")

    summary = {
        "dataset_id": manifest["dataset_id"],
        "version": manifest["version"],
        "source_count": len(sources),
        "case_count": len(cases),
        "answerable_count": sum(case["answerable"] for case in cases),
        "category_counts": category_counts,
        "fingerprint_sha256": dataset_fingerprint(dataset_root, manifest, cases),
    }
    return manifest, cases, summary


def _percentile_95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def _mean(values: Iterable[float]) -> float | None:
    materialized = list(values)
    return statistics.fmean(materialized) if materialized else None


def _fact_coverage(case: dict[str, Any], answer: str) -> float | None:
    facts = case["required_facts"]
    if not facts:
        return None
    normalized = answer.casefold()
    return sum(fact.casefold() in normalized for fact in facts) / len(facts)


def _validate_prediction(prediction: dict[str, Any]) -> None:
    prediction_id = prediction.get("id", "<missing-id>")
    required = {"id", "retrieved_evidence", "citations", "answer", "supported", "latency_ms"}
    optional = {"answer_correct", "explainability_score"}
    if not required.issubset(prediction) or set(prediction) - required - optional:
        raise DatasetError(f"{prediction_id} does not match the prediction contract")
    if not isinstance(prediction_id, str) or not prediction_id:
        raise DatasetError("Prediction id must be a non-empty string")
    if prediction["answer"] is not None and not isinstance(prediction["answer"], str):
        raise DatasetError(f"{prediction_id}.answer must be a string or null")
    if prediction["supported"] is not None and not isinstance(prediction["supported"], bool):
        raise DatasetError(f"{prediction_id}.supported must be boolean or null")
    if (prediction["answer"] is None) != (prediction["supported"] is None):
        raise DatasetError(f"{prediction_id}.answer and supported must both be null or both be set")
    if prediction["answer"] is None and prediction["citations"]:
        raise DatasetError(f"{prediction_id} cannot contain citations without an answer")
    latency = prediction["latency_ms"]
    if isinstance(latency, bool) or not isinstance(latency, (int, float)) or latency < 0 or not math.isfinite(latency):
        raise DatasetError(f"{prediction_id}.latency_ms must be a finite non-negative number")
    for field in ("retrieved_evidence", "citations"):
        value = prediction[field]
        if not isinstance(value, list):
            raise DatasetError(f"{prediction_id}.{field} must be a list")
        for item in value:
            _validate_evidence_shape(item, prediction_id)
    if "answer_correct" in prediction and prediction["answer_correct"] is not None:
        if not isinstance(prediction["answer_correct"], bool):
            raise DatasetError(f"{prediction_id}.answer_correct must be boolean or null")
        if prediction["answer"] is None:
            raise DatasetError(f"{prediction_id}.answer_correct requires an answer")
    if "explainability_score" in prediction and prediction["explainability_score"] is not None:
        score = prediction["explainability_score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 1 <= score <= 5:
            raise DatasetError(f"{prediction_id}.explainability_score must be between 1 and 5")
        if prediction["answer"] is None:
            raise DatasetError(f"{prediction_id}.explainability_score requires an answer")


def score_predictions(cases: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {case["id"]: case for case in cases}
    prediction_ids = [prediction.get("id") for prediction in predictions]
    if len(prediction_ids) != len(set(prediction_ids)):
        raise DatasetError("Prediction ids must be unique")
    if set(prediction_ids) != set(by_id):
        missing = sorted(set(by_id) - set(prediction_ids))
        extra = sorted(set(prediction_ids) - set(by_id))
        raise DatasetError(f"Predictions must cover every case; missing={missing}, extra={extra}")
    for prediction in predictions:
        _validate_prediction(prediction)

    recall_by_k: dict[int, list[float]] = {1: [], 3: [], 5: []}
    citation_matches = 0
    citation_total = 0
    gold_citation_total = 0
    supported_matches: list[float] = []
    fact_coverages: list[float] = []
    manual_scores: list[float] = []
    manual_by_category: dict[str, list[float]] = {category: [] for category in CATEGORIES}
    explainability: list[float] = []
    latencies: list[float] = []

    for prediction in predictions:
        case = by_id[prediction["id"]]
        gold = {_evidence_key(item) for item in case["gold_evidence"]}
        retrieved = [_evidence_key(item) for item in prediction["retrieved_evidence"]]
        citations = {_evidence_key(item) for item in prediction["citations"]}
        if case["answerable"]:
            for k in recall_by_k:
                recall_by_k[k].append(len(gold.intersection(retrieved[:k])) / len(gold))
        if prediction["answer"] is not None:
            if case["answerable"]:
                gold_citation_total += len(gold)
                coverage = _fact_coverage(case, prediction["answer"])
                if coverage is not None:
                    fact_coverages.append(coverage)
            citation_matches += len(gold.intersection(citations))
            citation_total += len(citations)
            supported_matches.append(float(prediction["supported"] == case["answerable"]))
        latencies.append(float(prediction["latency_ms"]))
        if prediction.get("answer_correct") is not None:
            score = float(prediction["answer_correct"])
            manual_scores.append(score)
            manual_by_category[case["category"]].append(score)
        if prediction.get("explainability_score") is not None:
            explainability.append(float(prediction["explainability_score"]))

    citation_precision = citation_matches / citation_total if citation_total else None
    citation_recall = citation_matches / gold_citation_total if gold_citation_total else None
    citation_f1 = None
    if citation_precision is not None and citation_recall is not None and citation_precision + citation_recall:
        citation_f1 = 2 * citation_precision * citation_recall / (citation_precision + citation_recall)

    return {
        "case_count": len(cases),
        "retrieval": {f"evidence_recall_at_{k}": _mean(values) for k, values in recall_by_k.items()},
        "citations": {
            "precision": citation_precision,
            "recall": citation_recall,
            "f1": citation_f1,
            "evaluation_coverage": len(supported_matches) / len(cases),
        },
        "answers": {
            "supported_or_refusal_accuracy": _mean(supported_matches),
            "required_fact_coverage": _mean(fact_coverages),
            "automatic_evaluation_coverage": len(supported_matches) / len(cases),
            "manual_answer_accuracy": _mean(manual_scores),
            "manual_grade_coverage": len(manual_scores) / len(cases),
            "cross_document_accuracy": _mean(manual_by_category["cross_document"]),
            "historical_trace_accuracy": _mean(manual_by_category["temporal"]),
        },
        "latency_ms": {
            "mean": _mean(latencies),
            "p95": _percentile_95(latencies),
        },
        "explainability": {
            "mean_score_1_to_5": _mean(explainability),
            "grade_coverage": len(explainability) / len(cases),
        },
    }


def _write_json(value: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    if output is None:
        print(rendered)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="Validate manifest, cases, and exact corpus evidence")
    validate.add_argument("--dataset", type=Path, required=True, help="Path to the evaluation directory")
    validate.add_argument("--output", type=Path, help="Optional JSON validation report")
    score = subparsers.add_parser("score", help="Score a complete prediction JSONL export")
    score.add_argument("--dataset", type=Path, required=True, help="Path to the evaluation directory")
    score.add_argument("--predictions", type=Path, required=True, help="Prediction JSONL file")
    score.add_argument("--output", type=Path, help="Optional JSON metrics report")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        _, cases, summary = validate_dataset(args.dataset)
        if args.command == "validate":
            _write_json(summary, args.output)
        else:
            predictions = read_jsonl(args.predictions)
            report = {
                "dataset": summary,
                "metrics": score_predictions(cases, predictions),
            }
            _write_json(report, args.output)
    except DatasetError as exc:
        raise SystemExit(f"evaluation dataset error: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
