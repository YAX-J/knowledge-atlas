"""Run the frozen evaluation set against one prepared Knowledge Atlas project.

The default is a keyword-only retrieval run and makes no provider calls. Vector
or hybrid modes require --allow-embedding-calls. Answer generation requires the
explicit --with-answers flag. Run output never includes credentials, database
URLs, full provider responses, or source bodies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.identity import DEVELOPMENT_USER_ID
from app.db.session import SessionLocal
from app.models.domain import SourceDocument, SourceStatus
from app.schemas.questions import AnswerDraft
from app.schemas.search import SearchRead
from app.services import deepseek
from app.services.projects import get_project
from app.services.search import search_knowledge
from scripts.evaluate_dataset import (
    DatasetError,
    SUPPORTED_CORPUS_SUFFIXES,
    score_predictions,
    validate_dataset,
)


Mode = Literal["keyword", "vector", "hybrid"]
MAX_ANSWER_EVIDENCE = 12


class EvaluationRunError(RuntimeError):
    """Raised for safe, user-actionable experiment preflight failures."""


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_valid_at(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def _corpus_hashes(dataset_root: Path, corpus_root_name: str) -> dict[str, Path]:
    corpus_root = dataset_root / corpus_root_name
    hashes: dict[str, Path] = {}
    for path in sorted(item for item in corpus_root.rglob("*") if item.is_file()):
        if path.suffix.lower() not in SUPPORTED_CORPUS_SUFFIXES:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in hashes:
            raise EvaluationRunError(
                f"Corpus files must have unique bytes: {hashes[digest].name} and {path.name}"
            )
        hashes[digest] = path
    return hashes


def map_project_sources(
    db: Session,
    *,
    dataset_root: Path,
    corpus_root_name: str,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict[uuid.UUID, str]:
    """Require an isolated project containing exactly one ready copy of each source."""
    get_project(db, user_id=user_id, project_id=project_id)
    expected = _corpus_hashes(dataset_root, corpus_root_name)
    sources = list(db.scalars(select(SourceDocument).where(
        SourceDocument.user_id == user_id,
        SourceDocument.project_id == project_id,
    ).order_by(SourceDocument.id)))
    if len(sources) != len(expected):
        raise EvaluationRunError(
            f"Evaluation project must contain exactly {len(expected)} sources; found {len(sources)}"
        )

    mapping: dict[uuid.UUID, str] = {}
    seen_hashes: set[str] = set()
    for source in sources:
        path = expected.get(source.content_sha256)
        if path is None:
            raise EvaluationRunError(
                f"Project source {source.original_name!r} is not part of the frozen corpus"
            )
        if source.status != SourceStatus.READY:
            raise EvaluationRunError(f"Project source {source.original_name!r} is not ready")
        if source.original_name != path.name:
            raise EvaluationRunError(
                f"Project source name {source.original_name!r} does not match corpus file {path.name!r}"
            )
        if source.content_sha256 in seen_hashes:
            raise EvaluationRunError(f"Project contains a duplicate copy of {source.original_name!r}")
        seen_hashes.add(source.content_sha256)
        mapping[source.id] = path.relative_to(dataset_root).as_posix()

    missing = [path.name for digest, path in expected.items() if digest not in seen_hashes]
    if missing:
        raise EvaluationRunError(f"Evaluation project is missing corpus sources: {missing}")
    return mapping


def _evidence_record(evidence: Any, source_paths: dict[uuid.UUID, str]) -> dict[str, Any]:
    source = source_paths.get(evidence.source_id)
    if source is None:
        raise EvaluationRunError("Retrieved formal evidence points outside the frozen corpus")
    return {
        "source": source,
        "start_line": evidence.start_line,
        "end_line": evidence.end_line,
        "quote": evidence.quote,
    }


def ordered_evidence(result: SearchRead) -> list[Any]:
    seen: set[uuid.UUID] = set()
    evidence = []
    for hit in result.items:
        for item in hit.evidence:
            if item.id in seen:
                continue
            seen.add(item.id)
            evidence.append(item)
    return evidence


def answer_from_result(
    *,
    settings: Settings,
    question: str,
    result: SearchRead,
    source_paths: dict[uuid.UUID, str],
    answer_fn: Callable[[Settings, str, list[dict[str, Any]]], AnswerDraft] = deepseek.answer_question,
) -> tuple[str, bool, list[dict[str, Any]], bool]:
    selected = ordered_evidence(result)[:MAX_ANSWER_EVIDENCE]
    if not selected:
        return (
            "现有已确认知识中没有足够的原文证据回答这个问题。",
            False,
            [],
            False,
        )
    payload = [{
        "id": str(item.id),
        "entity_name": next(
            hit.entity.name for hit in result.items if any(evidence.id == item.id for evidence in hit.evidence)
        ),
        "title": item.title,
        "start_line": item.start_line,
        "end_line": item.end_line,
        "quote": item.quote,
    } for item in selected]
    draft = answer_fn(settings, question, payload)
    by_id = {item.id: item for item in selected}
    unknown = set(draft.citation_ids) - set(by_id)
    if unknown:
        raise EvaluationRunError("Answer provider cited evidence outside this retrieval result")
    citations = [_evidence_record(by_id[item_id], source_paths) for item_id in draft.citation_ids]
    return draft.answer, draft.supported, citations, True


def build_prediction(
    *,
    db: Session,
    settings: Settings,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    case: dict[str, Any],
    mode: Mode,
    top_k: int,
    with_answers: bool,
    source_paths: dict[uuid.UUID, str],
    search_fn: Callable[..., SearchRead] = search_knowledge,
    answer_fn: Callable[[Settings, str, list[dict[str, Any]]], AnswerDraft] = deepseek.answer_question,
) -> tuple[dict[str, Any], bool]:
    started = time.perf_counter()
    result = search_fn(
        db,
        user_id=user_id,
        project_id=project_id,
        query=case["question"],
        types=[],
        valid_at=parse_valid_at(case["valid_at"]),
        top_k=top_k,
        mode=mode,
        settings=settings,
    )
    if mode in {"vector", "hybrid"}:
        if not result.eligible_count:
            raise EvaluationRunError("Vector experiment requires at least one eligible formal entity")
        if result.indexed_count != result.eligible_count:
            raise EvaluationRunError(
                f"Vector index is incomplete: {result.indexed_count}/{result.eligible_count} entities indexed"
            )

    retrieved = [_evidence_record(item, source_paths) for item in ordered_evidence(result)]
    answer: str | None = None
    supported: bool | None = None
    citations: list[dict[str, Any]] = []
    answer_provider_called = False
    if with_answers:
        answer, supported, citations, answer_provider_called = answer_from_result(
            settings=settings,
            question=case["question"],
            result=result,
            source_paths=source_paths,
            answer_fn=answer_fn,
        )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    return ({
        "id": case["id"],
        "retrieved_evidence": retrieved,
        "citations": citations,
        "answer": answer,
        "supported": supported,
        "latency_ms": elapsed_ms,
        "answer_correct": None,
        "explainability_score": None,
    }, answer_provider_called)


def run_evaluation(
    *,
    dataset_root: Path,
    project_id: uuid.UUID,
    output_dir: Path,
    modes: list[Mode],
    top_k: int,
    with_answers: bool,
    allow_embedding_calls: bool,
    settings: Settings,
    user_id: uuid.UUID = DEVELOPMENT_USER_ID,
) -> dict[str, Any]:
    manifest, cases, dataset_summary = validate_dataset(dataset_root)
    if len(modes) != len(set(modes)):
        raise EvaluationRunError("Modes must not contain duplicates")
    uses_embeddings = any(mode in {"vector", "hybrid"} for mode in modes)
    if uses_embeddings and not allow_embedding_calls:
        raise EvaluationRunError("Vector and hybrid modes require --allow-embedding-calls")
    if uses_embeddings and settings.embedding_api_key is None:
        raise EvaluationRunError("Embedding provider is not configured")
    if with_answers and settings.deepseek_api_key is None:
        raise EvaluationRunError("Answer provider is not configured")
    if output_dir.exists():
        raise EvaluationRunError(f"Output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)

    run_manifest: dict[str, Any] = {
        "run_id": str(uuid.uuid4()),
        "status": "running",
        "started_at": utc_iso(),
        "completed_at": None,
        "dataset": dataset_summary,
        "project_id": str(project_id),
        "modes": modes,
        "top_k_entities": top_k,
        "with_answers": with_answers,
        "timing_scope": "retrieval_and_answer" if with_answers else "retrieval_only",
        "provider_authorization": {
            "embedding_calls": allow_embedding_calls and uses_embeddings,
            "answer_calls": with_answers,
        },
        "models": {
            "embedding": settings.embedding_model if uses_embeddings else None,
            "answer": settings.deepseek_model if with_answers else None,
        },
        "successful_provider_call_counts": {"embedding": 0, "answer": 0},
        "outputs": {},
    }
    manifest_path = output_dir / "run.json"
    _write_json(manifest_path, run_manifest)

    try:
        with SessionLocal() as db:
            source_paths = map_project_sources(
                db,
                dataset_root=dataset_root,
                corpus_root_name=manifest["corpus_root"],
                project_id=project_id,
                user_id=user_id,
            )
            for mode in modes:
                partial_path = output_dir / f"{mode}.partial.jsonl"
                final_path = output_dir / f"{mode}.jsonl"
                predictions = []
                for case in cases:
                    prediction, answer_called = build_prediction(
                        db=db,
                        settings=settings,
                        user_id=user_id,
                        project_id=project_id,
                        case=case,
                        mode=mode,
                        top_k=top_k,
                        with_answers=with_answers,
                        source_paths=source_paths,
                    )
                    predictions.append(prediction)
                    _append_jsonl(partial_path, prediction)
                    if mode in {"vector", "hybrid"}:
                        run_manifest["successful_provider_call_counts"]["embedding"] += 1
                    if answer_called:
                        run_manifest["successful_provider_call_counts"]["answer"] += 1
                partial_path.replace(final_path)
                metrics_path = output_dir / f"{mode}.metrics.json"
                _write_json(metrics_path, score_predictions(cases, predictions))
                run_manifest["outputs"][mode] = {
                    "predictions": final_path.name,
                    "metrics": metrics_path.name,
                    "case_count": len(predictions),
                }
                _write_json(manifest_path, run_manifest)
        run_manifest["status"] = "succeeded"
        run_manifest["completed_at"] = utc_iso()
        _write_json(manifest_path, run_manifest)
        return run_manifest
    except Exception as exc:
        run_manifest["status"] = "failed"
        run_manifest["completed_at"] = utc_iso()
        run_manifest["error_type"] = type(exc).__name__
        if isinstance(exc, (AppError, deepseek.QuestionError)):
            run_manifest["error_code"] = exc.code
        _write_json(manifest_path, run_manifest)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True, help="Path to evaluation/")
    parser.add_argument("--project-id", type=uuid.UUID, required=True, help="Prepared isolated project UUID")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for run outputs")
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=("keyword", "vector", "hybrid"),
        default=["keyword"],
        help="Experiment modes; default keyword makes no provider calls",
    )
    parser.add_argument("--top-k", type=int, default=5, choices=range(1, 51), metavar="1..50")
    parser.add_argument(
        "--allow-embedding-calls",
        action="store_true",
        help="Explicitly authorize embedding-provider calls for vector/hybrid modes",
    )
    parser.add_argument(
        "--with-answers",
        action="store_true",
        help="Explicitly authorize answer-provider calls when retrieved evidence exists",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_evaluation(
            dataset_root=args.dataset.resolve(),
            project_id=args.project_id,
            output_dir=args.output_dir.resolve(),
            modes=args.modes,
            top_k=args.top_k,
            with_answers=args.with_answers,
            allow_embedding_calls=args.allow_embedding_calls,
            settings=get_settings(),
        )
    except (DatasetError, EvaluationRunError) as exc:
        print(f"Evaluation run failed: {exc}", file=sys.stderr)
        return 2
    except AppError as exc:
        print(f"Evaluation run failed with application error {exc.code}", file=sys.stderr)
        return 2
    except deepseek.QuestionError as exc:
        print(f"Evaluation run failed with answer-provider error {exc.code}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Evaluation run failed ({type(exc).__name__}); inspect local logs without exposing secrets.", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
