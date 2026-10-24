"""Explicit synthetic DeepSeek acceptance, frozen retrieval replay and blind review.

At most 172 DeepSeek requests: 120 answers, ten single-step analyses, forty
tool-agent turns and two extractions. No embeddings, GitHub or DB writes.
"""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import uuid

from app.core.config import get_settings
from app.core.errors import AppError
from app.services import deepseek
from app.services.markdown import parse_markdown
from app.services.model_usage import usage_budget
from scripts.evaluate_calls import benchmark
from scripts.evaluate_dataset import read_jsonl, score_predictions, validate_dataset


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def answer_replay(settings, *, root: Path, cases: list[dict], frozen: list[dict]) -> list[dict]:
    by_id = {item["id"]: item for item in frozen}
    if len(by_id) != len(cases) or set(by_id) != {case["id"] for case in cases}:
        raise ValueError("Frozen retrieval must cover every case")
    predictions = []
    for case in cases:
        started = time.perf_counter()
        evidence = by_id[case["id"]]["retrieved_evidence"][:12]
        seen = set()
        selected = []
        for item in evidence:
            path = (root / item["source"]).resolve()
            if not path.is_relative_to((root / "corpus").resolve()):
                raise ValueError("Evidence outside corpus")
            text = "\n".join(path.read_text(encoding="utf-8").splitlines()[item["start_line"] - 1:item["end_line"]])
            if not item["quote"] or item["quote"] not in text:
                raise ValueError("Frozen quote no longer matches source")
            identifier = uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(item, ensure_ascii=False, sort_keys=True))
            if identifier not in seen:
                seen.add(identifier)
                selected.append((identifier, item))
        answer, supported, citations = "现有资料没有足够的证据回答。", False, []
        if selected:
            draft = deepseek.answer_question(settings, case["question"], [
                {"id": str(identifier), "entity_name": item["source"], "title": item["source"],
                 "start_line": item["start_line"], "end_line": item["end_line"], "quote": item["quote"]}
                for identifier, item in selected])
            by_evidence = dict(selected)
            if set(draft.citation_ids) - set(by_evidence):
                raise ValueError("Provider returned a citation outside frozen evidence")
            answer, supported = draft.answer, draft.supported
            citations = [by_evidence[key] for key in draft.citation_ids]
        predictions.append({"id": case["id"], "retrieved_evidence": by_id[case["id"]]["retrieved_evidence"],
                            "citations": citations, "answer": answer, "supported": supported,
                            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                            "answer_correct": None, "explainability_score": None})
    return predictions


def blind_packet(cases, modes, output: Path):
    by_case = {case["id"]: case for case in cases}
    rows = []
    for mode, predictions in modes.items():
        for item in predictions:
            case = by_case[item["id"]]
            rows.append((mode, item, case))
    random.Random(20261024).shuffle(rows)
    key = {}
    with (output / "blind-review.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["review_id", "question", "answer", "citations", "gold_answer",
                                                    "required_facts", "reviewer", "answer_correct", "explainability_score"])
        writer.writeheader()
        for number, (mode, item, case) in enumerate(rows, 1):
            identifier = f"review-{number:03}"
            key[identifier] = {"mode": mode, "case_id": case["id"]}
            writer.writerow({"review_id": identifier, "question": case["question"], "answer": item["answer"],
                             "citations": json.dumps(item["citations"], ensure_ascii=False), "gold_answer": case["gold_answer"],
                             "required_facts": json.dumps(case["required_facts"], ensure_ascii=False)})
    save(output / "grading-key.json", key)


def run_acceptance(*, dataset: Path, retrieval: Path, output: Path, settings, allow_model_calls: bool):
    if not allow_model_calls:
        raise ValueError("--allow-model-calls is required")
    if not settings.deepseek_api_key or not settings.deepseek_api_key.get_secret_value().strip():
        raise ValueError("DeepSeek configuration is missing")
    _, cases, summary = validate_dataset(dataset)
    frozen_run = json.loads((retrieval / "run.json").read_text(encoding="utf-8"))
    if frozen_run["status"] != "succeeded" or frozen_run["dataset"] != summary:
        raise ValueError("Frozen retrieval manifest does not match the dataset")
    output.mkdir(parents=True, exist_ok=False)
    report = {"status": "running", "dataset": summary, "model": settings.deepseek_model,
              "started_at": datetime.now(timezone.utc).isoformat(), "answer_input": "frozen_retrieval_replay",
              "manual_grading_coverage": 0, "billing_cost": None, "phases": {}}
    report_path = output / "acceptance.json"
    save(report_path, report)
    modes = {}
    with usage_budget(172) as meter:
        try:
            for mode in ("static", "single_step", "tools"):
                print(f"Call analysis: {mode}", flush=True)
                predictions, result = benchmark(dataset / "calls", mode=mode, settings=settings)
                (output / f"calls-{mode}.jsonl").write_text("".join(json.dumps(item) + "\n" for item in predictions), encoding="utf-8")
                save(output / f"calls-{mode}.metrics.json", result)
                report["phases"][f"calls-{mode}"] = "succeeded"
                report["usage"] = meter.summary()
                save(report_path, report)
            for mode in ("keyword", "vector", "hybrid"):
                print(f"Answer replay: {mode}", flush=True)
                predictions = answer_replay(settings, root=dataset, cases=cases, frozen=read_jsonl(retrieval / f"{mode}.jsonl"))
                modes[mode] = predictions
                (output / f"answers-{mode}.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in predictions), encoding="utf-8")
                save(output / f"answers-{mode}.metrics.json", score_predictions(cases, predictions))
                report["phases"][f"answers-{mode}"] = "succeeded"
                report["usage"] = meter.summary()
                save(report_path, report)
            extraction = []
            for name in ("01_project_scope.md", "11_review_policy.md"):
                print(f"Extraction: {name}", flush=True)
                path = dataset / "corpus" / "docs" / name
                chunks = parse_markdown(path.read_text(encoding="utf-8"), source_id=uuid.uuid5(uuid.NAMESPACE_URL, name))
                payload = [{"chunk_id": str(chunk.id), "content": chunk.content} for chunk in chunks]
                draft = deepseek.extract_candidates(settings, payload)
                by_id = {chunk.id: chunk.content for chunk in chunks}
                exact = all(ref.chunk_id in by_id and ref.quote in by_id[ref.chunk_id]
                            for item in [*draft.entities, *draft.relations] for ref in item.evidence)
                if not exact:
                    raise ValueError("Real extraction returned invalid source evidence")
                extraction.append({"source": f"corpus/docs/{name}", "entities": len(draft.entities),
                                   "relations": len(draft.relations), "all_evidence_exact": exact,
                                   "semantic_human_review": "pending"})
            save(output / "extraction.json", extraction)
            blind_packet(cases, modes, output)
            report.update(status="succeeded", blind_review_items=sum(len(items) for items in modes.values()),
                          human_review_status="pending")
        except Exception as exc:
            report.update(status="failed", error_type=type(exc).__name__)
            if isinstance(exc, (AppError, deepseek.ExtractionError, deepseek.QuestionError, deepseek.CallAgentError)):
                report["error_code"] = exc.code
            raise
        finally:
            report.update(usage=meter.summary(), completed_at=datetime.now(timezone.utc).isoformat())
            save(report_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--retrieval-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-model-calls", action="store_true")
    args = parser.parse_args()
    try:
        result = run_acceptance(dataset=args.dataset.resolve(), retrieval=args.retrieval_dir,
                                output=args.output_dir, settings=get_settings(), allow_model_calls=args.allow_model_calls)
    except Exception as exc:
        print(f"Model acceptance failed ({type(exc).__name__}); inspect the sanitized acceptance report.", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
