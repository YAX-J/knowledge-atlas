"""Build one explicit embedding index and compare three retrieval baselines.

Only accepts a successful curated-project preparation report. Answer generation
is disabled. --allow-embedding-calls authorizes indexing and 80 query requests.
"""

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import uuid
from unittest.mock import patch

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.identity import DEVELOPMENT_USER_ID
from app.db.session import engine as configured_engine
from app.services import embeddings
from scripts.evaluation_snapshot import project_snapshot
from scripts.prepare_evaluation import load_fixture, PreparationError
from scripts.run_evaluation import EvaluationRunError, run_evaluation


def _save(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_baselines(*, dataset_root: Path, preparation_report: Path, output_dir: Path,
                  settings, engine, allow_embedding_calls: bool, embedding_batch_size: int = 10) -> dict:
    if not allow_embedding_calls:
        raise EvaluationRunError("Explicit --allow-embedding-calls is required for the three-baseline comparison")
    if not 1 <= embedding_batch_size <= 100:
        raise EvaluationRunError("Embedding batch size must be between 1 and 100")
    settings = settings.model_copy(update={"embedding_batch_size": embedding_batch_size})
    if not (settings.embedding_api_key and settings.embedding_api_key.get_secret_value().strip()
            and settings.embedding_base_url.strip() and settings.embedding_model.strip()):
        raise EvaluationRunError("Embedding provider is not configured")
    prepared = json.loads(preparation_report.read_text(encoding="utf-8"))
    _, summary, fingerprint = load_fixture(dataset_root)
    if (prepared.get("status") != "succeeded" or prepared.get("protocol") != "curated-review-replay-v1"
            or prepared.get("fixture_fingerprint_sha256") != fingerprint or prepared.get("dataset") != summary):
        raise EvaluationRunError("Preparation report does not match the successful frozen fixture")
    project_id = uuid.UUID(prepared["project_id"])
    with Session(engine) as db:
        current = project_snapshot(db, user_id=DEVELOPMENT_USER_ID, project_id=project_id)
    if current["knowledge_sha256"] != prepared["snapshot"]["knowledge_sha256"]:
        raise EvaluationRunError("Prepared project knowledge changed; create a new isolated experiment project")
    output_dir.mkdir(parents=True, exist_ok=False)
    report_path = output_dir / "baselines.json"
    calls = {"attempted": 0, "successful": 0, "failed": 0, "texts": 0, "input_characters": 0}
    report = {"status": "running", "dataset": summary, "fixture_fingerprint_sha256": fingerprint,
              "project_id": str(project_id), "embedding_model": settings.embedding_model,
              "dimensions": settings.embedding_dimensions, "answer_calls": 0,
              "embedding_batch_size": embedding_batch_size,
              "embedding_calls": calls, "billing_tokens": None, "billing_cost": None,
              "started_at": datetime.now(timezone.utc).isoformat()}
    _save(report_path, report)
    original_embed = embeddings.embed_texts

    def measured_embed(configuration, texts):
        calls["attempted"] += 1
        calls["texts"] += len(texts)
        calls["input_characters"] += sum(len(text) for text in texts)
        try:
            result = original_embed(configuration, texts)
        except Exception:
            calls["failed"] += 1
            _save(report_path, report)
            raise
        calls["successful"] += 1
        _save(report_path, report)
        return result

    started = time.perf_counter()
    try:
        # Standalone orchestration instrumentation; never patch an API process.
        with patch.object(embeddings, "embed_texts", side_effect=measured_embed):
            with Session(engine) as db:
                report["index"] = embeddings.rebuild_project_embeddings(
                    db, user_id=DEVELOPMENT_USER_ID, project_id=project_id, settings=settings,
                )
            result = run_evaluation(
                dataset_root=dataset_root, project_id=project_id, output_dir=output_dir / "retrieval",
                modes=["keyword", "vector", "hybrid"], top_k=5, with_answers=False,
                allow_embedding_calls=True, settings=settings,
                session_factory=sessionmaker(bind=engine, expire_on_commit=False),
            )
        report["project_snapshot"] = result["project_snapshot"]
        rows = []
        for mode in ("keyword", "vector", "hybrid"):
            metrics = json.loads((output_dir / "retrieval" / f"{mode}.metrics.json").read_text())
            diagnostics = [json.loads(line) for line in (output_dir / "retrieval" / f"{mode}.diagnostics.jsonl").read_text(encoding="utf-8").splitlines()]
            rows.append({"mode": mode, **metrics["retrieval"],
                         "mean_latency_ms": metrics["latency_ms"]["mean"],
                         "p95_latency_ms": metrics["latency_ms"]["p95"],
                         "positive_graph_hits": sum(bool(hit["graph_score"]) for row in diagnostics for hit in row["hits"]),
                         "answer_evaluation_coverage": metrics["answers"]["automatic_evaluation_coverage"]})
        with (output_dir / "comparison.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        lines = ["# Frozen synthetic retrieval baselines", "",
                 "Answers are not evaluated. Latency includes query embedding for vector/hybrid.", "",
                 "| Mode | Recall@1 | Recall@3 | Recall@5 | Mean ms | P95 ms | Positive graph hits |",
                 "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for row in rows:
            lines.append(f"| {row['mode']} | {row['evidence_recall_at_1']:.4f} | {row['evidence_recall_at_3']:.4f} | {row['evidence_recall_at_5']:.4f} | {row['mean_latency_ms']:.1f} | {row['p95_latency_ms']:.1f} | {row['positive_graph_hits']} |")
        (output_dir / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        report.update(status="succeeded", comparison=rows)
    except Exception as exc:
        report.update(status="failed", error_type=type(exc).__name__)
        if isinstance(exc, AppError):
            report["error_code"] = exc.code
        raise
    finally:
        report.update(completed_at=datetime.now(timezone.utc).isoformat(),
                      elapsed_seconds=round(time.perf_counter() - started, 3))
        _save(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--preparation-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-embedding-calls", action="store_true")
    parser.add_argument("--embedding-batch-size", type=int, default=10, choices=range(1, 101), metavar="1..100")
    args = parser.parse_args()
    try:
        result = run_baselines(dataset_root=args.dataset.resolve(), preparation_report=args.preparation_report,
                               output_dir=args.output_dir, settings=get_settings(), engine=configured_engine,
                               allow_embedding_calls=args.allow_embedding_calls,
                               embedding_batch_size=args.embedding_batch_size)
    except (EvaluationRunError, PreparationError) as exc:
        print(f"Baseline experiment failed: {exc}", file=sys.stderr)
        return 2
    except AppError as exc:
        print(f"Baseline experiment failed with application error {exc.code}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Baseline experiment failed ({type(exc).__name__}); consult the local report without exposing credentials.", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
