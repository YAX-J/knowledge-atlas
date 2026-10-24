"""Validate and benchmark frozen cross-file calls; default is provider-free."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
import uuid

from app.core.config import get_settings
from app.models.domain import SourceDocument, SourceStatus
from app.services import code_agent


class CallDatasetError(ValueError):
    pass


def validate_calls(root: Path) -> tuple[dict, list[dict], dict]:
    root = root.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    cases = [json.loads(line) for line in (root / manifest["cases_file"]).read_text(encoding="utf-8").splitlines() if line]
    files = sorted(path for path in (root / "corpus").rglob("*") if path.is_file())
    if len(files) != manifest["source_count"] or len(cases) != manifest["case_count"]:
        raise CallDatasetError("Manifest source/case counts do not match")
    if len({case["id"] for case in cases}) != len(cases):
        raise CallDatasetError("Duplicate case IDs")
    if set(case["language"] for case in cases) != set(manifest["languages"]):
        raise CallDatasetError("Language coverage does not match")

    def exact(path, line, quote):
        target = (root / path).resolve()
        if not target.is_relative_to(root / "corpus") or not target.is_file():
            raise CallDatasetError("Evidence path must stay inside the corpus")
        lines = target.read_text(encoding="utf-8").splitlines()
        if not isinstance(line, int) or isinstance(line, bool) or not 1 <= line <= len(lines) or lines[line - 1] != quote:
            raise CallDatasetError("Gold source line does not match exactly")

    for case in cases:
        exact(case["source"], case["line"], case["quote"])
        resolution, targets = case["resolution"], case["targets"]
        if (resolution not in {"resolved", "ambiguous", "unresolved"}
                or resolution == "resolved" and len(targets) != 1
                or resolution == "ambiguous" and len(targets) < 2
                or resolution == "unresolved" and targets):
            raise CallDatasetError("Resolution and targets disagree")
        for target in targets:
            exact(target["source"], target["line"], target["quote"])
            if Path(target["source"]).parent != Path(case["source"]).parent:
                raise CallDatasetError("Target is outside the case repository")
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode())
    digest.update(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode())
    for path in files:
        if not path.resolve().is_relative_to(root / "corpus"):
            raise CallDatasetError("Corpus symlink escapes the dataset")
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    summary = {"dataset_id": manifest["dataset_id"], "version": manifest["version"],
               "case_count": len(cases), "source_count": len(files),
               "languages": dict(Counter(case["language"] for case in cases)),
               "scenarios": dict(Counter(case["scenario"] for case in cases)),
               "fingerprint_sha256": digest.hexdigest()}
    return manifest, cases, summary


def source_snapshot(root: Path, language: str) -> tuple[SourceDocument, list[SourceDocument]]:
    project_id = uuid.uuid5(uuid.NAMESPACE_URL, f"ka-call-benchmark:{language}")
    records = []
    for path in sorted((root / "corpus" / language).iterdir()):
        content = path.read_text(encoding="utf-8")
        relative = path.relative_to(root).as_posix()
        records.append(SourceDocument(
            id=uuid.uuid5(project_id, relative), user_id=project_id, project_id=project_id,
            repository_id=project_id, original_name=path.name, relative_path=relative,
            source_type=language, content=content, size_bytes=len(content.encode()),
            content_sha256=hashlib.sha256(content.encode()).hexdigest(), status=SourceStatus.READY,
        ))
    main = next(item for item in records if item.original_name.startswith("main."))
    return main, [item for item in records if item is not main]


def score_calls(cases: list[dict], predictions: list[dict]) -> dict:
    by_id = {item["id"]: item for item in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {case["id"] for case in cases}:
        raise CallDatasetError("Predictions must cover every case exactly once")
    counts = {"tp": 0, "fp": 0, "fn": 0, "correct": 0, "candidate_present": 0}
    groups = {}
    unresolved = []
    resolved = []
    for case in cases:
        prediction = by_id[case["id"]]
        gold = {(target["source"], target["line"]) for target in case["targets"]}
        actual = {(target["source"], target["line"]) for target in prediction["targets"]}
        correct = not prediction.get("error_code") and prediction["resolution"] == case["resolution"] and actual == gold
        counts["tp"] += len(gold & actual)
        counts["fp"] += len(actual - gold)
        counts["fn"] += len(gold - actual)
        counts["correct"] += correct
        counts["candidate_present"] += bool(prediction["candidate_present"])
        groups.setdefault(case["language"], []).append(correct)
        if case["resolution"] == "unresolved":
            unresolved.append(prediction["resolution"] == "unresolved")
        if prediction["resolution"] == "resolved":
            resolved.append(correct)
    precision = counts["tp"] / (counts["tp"] + counts["fp"]) if counts["tp"] + counts["fp"] else None
    recall = counts["tp"] / (counts["tp"] + counts["fn"]) if counts["tp"] + counts["fn"] else None
    return {"case_count": len(cases), "exact_decision_accuracy": counts["correct"] / len(cases),
            "target_precision": precision, "target_recall": recall,
            "target_f1": 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else 0.0,
            "candidate_coverage": counts["candidate_present"] / len(cases),
            "resolved_precision": statistics.mean(resolved) if resolved else None,
            "unresolved_accuracy": statistics.mean(unresolved) if unresolved else None,
            "by_language": {language: statistics.mean(values) for language, values in groups.items()}}


def benchmark(root: Path, *, mode: str, settings) -> tuple[list[dict], dict]:
    _, cases, summary = validate_calls(root)
    predictions, runs = [], []
    for language in summary["languages"]:
        source, related = source_snapshot(root, language)
        started = time.perf_counter()
        if mode == "static":
            calls, targets, *_ = (code_agent._java_candidates(source, related) if language == "java"
                                 else code_agent._non_java_candidates(source, related))
            decisions = {call.line: {"resolution": "resolved" if len(call.candidate_ids) == 1 else "ambiguous",
                                     "targets": [{"source": targets[key].source_path, "line": targets[key].start_line} for key in call.candidate_ids]}
                         for call in calls}
            provider_count = tool_count = 0
        else:
            result = code_agent.analyze_snapshot(source=source, related=related, settings=settings, strategy=mode)
            targets = {item.id: item for item in result.related_symbols}
            decisions = {call.line: {"resolution": call.resolution,
                                     "targets": [{"source": targets[key].source_path, "line": targets[key].start_line} for key in call.target_ids]}
                         for call in result.calls}
            provider_count, tool_count = result.provider_call_count, result.tool_call_count
        runs.append({"language": language, "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                     "provider_calls": provider_count, "tool_calls": tool_count})
        for case in (item for item in cases if item["language"] == language):
            prediction = decisions.get(case["line"], {"resolution": "unresolved", "targets": []})
            predictions.append({"id": case["id"], "candidate_present": case["line"] in decisions, **prediction})
    return predictions, {"dataset": summary, "mode": mode, "metrics": score_calls(cases, predictions), "runs": runs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--mode", choices=["static", "single_step", "tools"], default="static")
    parser.add_argument("--allow-model-calls", action="store_true")
    args = parser.parse_args()
    try:
        _, _, summary = validate_calls(args.dataset)
        if args.validate_only:
            print(json.dumps(summary, indent=2))
            return 0
        if args.mode != "static" and not args.allow_model_calls:
            raise CallDatasetError("Model modes require --allow-model-calls")
        if args.output_dir is None:
            raise CallDatasetError("--output-dir is required")
        args.output_dir.mkdir(parents=True, exist_ok=False)
        predictions, report = benchmark(args.dataset, mode=args.mode, settings=get_settings())
        (args.output_dir / "predictions.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in predictions), encoding="utf-8")
        (args.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Call evaluation failed ({type(exc).__name__}); check dataset/configuration without exposing provider responses.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
