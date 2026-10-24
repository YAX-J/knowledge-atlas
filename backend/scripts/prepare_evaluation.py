"""Replay a curated synthetic fixture into a new evaluation project.

Run as a standalone CLI, never inside an API/Worker process. A scoped synthetic
clock replays ordinary review/promotion without adding a backdating API. Every
service commit is a savepoint inside one outer transaction. No providers run.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Annotated
import uuid
from unittest.mock import patch

from pydantic import AwareDatetime, Field, StringConstraints
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.identity import DEVELOPMENT_USER_ID
from app.db.session import engine as configured_engine
from app.models.domain import (
    CandidateKnowledge, ProcessingTask, Project, ReviewEvent, ReviewStatus,
    SourceChunk, SourceDocument, TaskStatus,
)
from app.models.evolution import KnowledgeChange
from app.models.graph import KnowledgeEntity, KnowledgeEvidence, KnowledgeRelationship
from app.schemas.evolution import ChangeCreate
from app.schemas.knowledge import EntityType, Name, RelationType, ReviewResolve, StrictModel
from app.schemas.repositories import RepositoryResolve
from app.services import evolution, graph, ingestion, knowledge, parsing, repositories
from scripts.evaluate_dataset import DatasetError, validate_dataset
from scripts.evaluation_snapshot import project_snapshot


FIXTURE_FILE = "reviewed_graph.json"
FIXTURE_PROTOCOL = "curated-review-replay-v1"
LocalId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,39}$")]
LineNumber = Annotated[int, Field(strict=True, ge=1)]


class PreparationError(ValueError):
    """A fixture or target cannot safely be used for an experiment."""


class FixtureEntity(StrictModel):
    id: LocalId
    type: EntityType
    name: Name
    lines: list[LineNumber] = Field(min_length=1, max_length=5)


class FixtureRelation(StrictModel):
    id: LocalId
    type: RelationType
    source: LocalId
    target: LocalId
    lines: list[LineNumber] = Field(min_length=1, max_length=5)


class FixtureSource(StrictModel):
    source: str
    available_at: AwareDatetime
    entities: list[FixtureEntity] = Field(min_length=1, max_length=50)
    relations: list[FixtureRelation] = Field(default_factory=list, max_length=100)


class FixtureChange(StrictModel):
    new: LocalId
    old: LocalId
    effective_at: AwareDatetime
    evidence_line: LineNumber
    reason: str = Field(min_length=1, max_length=2000)


class ReviewedFixture(StrictModel):
    fixture_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    dataset_id: str
    dataset_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: str = Field(min_length=1)
    sources: list[FixtureSource] = Field(min_length=1, max_length=100)
    changes: list[FixtureChange] = Field(max_length=100)


def _digest(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def load_fixture(dataset_root: Path) -> tuple[ReviewedFixture, dict, str]:
    """Validate all annotations and time visibility before touching a database."""
    manifest, cases, summary = validate_dataset(dataset_root)
    fixture = ReviewedFixture.model_validate_json((dataset_root / FIXTURE_FILE).read_bytes())
    if fixture.dataset_id != summary["dataset_id"] or fixture.dataset_fingerprint_sha256 != summary["fingerprint_sha256"]:
        raise PreparationError("Curated fixture does not match the frozen dataset fingerprint")
    root = dataset_root.resolve()
    corpus = (root / manifest["corpus_root"]).resolve()
    expected = {path.relative_to(root).as_posix() for path in corpus.rglob("*") if path.is_file()}
    if len(fixture.sources) != len(expected) or {item.source for item in fixture.sources} != expected:
        raise PreparationError("Curated fixture must cover every corpus source exactly once")
    now = datetime.now(timezone.utc)
    owners: dict[str, FixtureSource] = {}
    entities: dict[str, FixtureEntity] = {}
    for source in fixture.sources:
        path = (root / source.source).resolve()
        if not path.is_relative_to(corpus):
            raise PreparationError("Fixture source must stay inside the frozen corpus")
        if source.available_at > now:
            raise PreparationError("Fixture source availability cannot be in the future")
        lines = path.read_text(encoding="utf-8").splitlines()
        local = {item.id for item in source.entities}
        for item in [*source.entities, *source.relations]:
            if item.id in owners:
                raise PreparationError(f"Duplicate fixture ID: {item.id}")
            owners[item.id] = source
            if len(set(item.lines)) != len(item.lines):
                raise PreparationError(f"Duplicate evidence lines: {item.id}")
            if any(line > len(lines) or not lines[line - 1].strip() or len(lines[line - 1].strip()) > 1000 for line in item.lines):
                raise PreparationError(f"Invalid evidence lines: {item.id}")
            if isinstance(item, FixtureRelation):
                if item.source not in local or item.target not in local:
                    raise PreparationError("Semantic relation endpoints must belong to the same source")
                if item.type == "SUPERSEDES":
                    raise PreparationError("Use a reviewed evolution change for historical replacement")
            else:
                entities[item.id] = item
    source_by_path = {item.source: item for item in fixture.sources}
    # Gold cases are checked for time leakage, never used to generate candidates.
    for case in cases:
        if case["valid_at"] is None:
            continue
        at = datetime.fromisoformat(case["valid_at"].replace("Z", "+00:00"))
        if any(source_by_path[item["source"]].available_at > at for item in case["gold_evidence"]):
            raise PreparationError(f"Gold evidence is unavailable at the requested historical time: {case['id']}")
    changed_old, changed_new = set(), set()
    for change in sorted(fixture.changes, key=lambda item: item.effective_at):
        if change.new not in entities or change.old not in entities or change.new == change.old:
            raise PreparationError("Evolution endpoints must reference different fixture entities")
        if entities[change.new].type != entities[change.old].type:
            raise PreparationError("Evolution endpoints must have the same entity type")
        if change.old in changed_old or change.new in changed_new or change.new in changed_old:
            raise PreparationError("Evolution fixture must be a chronological linear chain")
        changed_old.add(change.old)
        changed_new.add(change.new)
        if not max(owners[change.new].available_at, owners[change.old].available_at) <= change.effective_at <= now:
            raise PreparationError("Evolution time must follow both source availability times")
        if change.evidence_line not in entities[change.new].lines:
            raise PreparationError("Evolution evidence must belong to the new entity")
    return fixture, summary, _digest(fixture.model_dump(mode="json"))


@contextmanager
def _replay_clock(at: datetime):
    """Only the standalone experiment process sees this synthetic clock."""
    with patch.object(graph, "utc_now", return_value=at):
        yield


def _references(db: Session, source: SourceDocument, lines: list[int]) -> list[dict]:
    chunks = list(db.scalars(select(SourceChunk).where(
        SourceChunk.source_id == source.id, SourceChunk.user_id == source.user_id,
        SourceChunk.project_id == source.project_id,
    ).order_by(SourceChunk.position)))
    source_lines = source.content.splitlines()
    result = []
    for line in lines:
        quote = source_lines[line - 1].strip()
        matches = [chunk for chunk in chunks if chunk.start_line <= line <= chunk.end_line and quote in chunk.content]
        if len(matches) != 1:
            raise PreparationError("Fixture evidence must map to exactly one parsed source chunk")
        chunk = matches[0]
        # Promotion recomputes positions with the ordinary exact-quote validator.
        offset = chunk.content.index(quote)
        if chunk.start_line + chunk.content[:offset].count("\n") != line:
            raise PreparationError("A repeated quote would resolve to the wrong evidence line")
        result.append({"chunk_id": str(chunk.id), "quote": quote, "start_line": line,
                       "end_line": line, "heading_path": chunk.heading_path})
    return result


def _populate(db: Session, *, fixture: ReviewedFixture, dataset_root: Path,
              project_id: uuid.UUID, user_id: uuid.UUID, settings: Settings,
              provenance: dict) -> dict:
    if db.get(Project, project_id) is not None:
        raise PreparationError("Project ID already exists; initialization only creates new projects")
    project = Project(id=project_id, user_id=user_id, name=f"[EVAL] {fixture.fixture_id}",
                      description=json.dumps(provenance, ensure_ascii=False, sort_keys=True))
    db.add(project)
    db.commit()
    repository = repositories.resolve_repository(
        db, user_id=user_id, project_id=project_id,
        repository_in=RepositoryResolve(name=fixture.fixture_id, kind="local_folder"),
    )
    records: dict[str, uuid.UUID] = {}
    formal: dict[str, uuid.UUID] = {}
    source_ids: dict[str, str] = {}
    for annotation in sorted(fixture.sources, key=lambda item: (item.available_at, item.source)):
        path = dataset_root / annotation.source
        source, task, reused = ingestion.create_source_and_task_from_bytes(
            db, settings=settings, user_id=user_id, project_id=project_id,
            filename=path.name, raw_content=path.read_bytes(), source_type=None,
            relative_path=annotation.source.removeprefix("corpus/"), repository_id=repository.id,
        )
        if reused:
            raise PreparationError("Unexpected duplicate corpus content")
        task = parsing.run_task(db, user_id=user_id, task_id=task.id, settings=settings)
        if task.status != TaskStatus.SUCCEEDED:
            raise PreparationError(f"Corpus parsing failed: {annotation.source}")
        source_ids[annotation.source] = str(source.id)
        task_id = knowledge.extraction_task_id(source.id)
        db.add(ProcessingTask(
            id=task_id, user_id=user_id, project_id=project_id, source_id=source.id,
            type=knowledge.EXTRACTION_TASK_TYPE, status=TaskStatus.SUCCEEDED,
            stage="candidates_ready", progress=100,
            started_at=annotation.available_at, completed_at=annotation.available_at,
        ))
        db.flush()
        for item in [*annotation.entities, *annotation.relations]:
            records[item.id] = uuid.uuid5(project_id, f"{FIXTURE_PROTOCOL}:{item.id}")
        for item in [*annotation.entities, *annotation.relations]:
            relation = isinstance(item, FixtureRelation)
            refs = _references(db, source, item.lines)
            payload = {
                "kind": "relation" if relation else "entity", "local_id": item.id,
                "evidence": refs, "model": "curated-fixture", "prompt_version": FIXTURE_PROTOCOL,
                "fixture_fingerprint_sha256": provenance["fixture_fingerprint_sha256"],
                "synthetic_valid_from": annotation.available_at.isoformat(),
            }
            if relation:
                payload.update(source_candidate_id=str(records[item.source]), target_candidate_id=str(records[item.target]))
            candidate = CandidateKnowledge(
                id=records[item.id], user_id=user_id, project_id=project_id, source_id=source.id,
                task_id=task_id, candidate_type=item.type,
                name=f"{item.source} → {item.target}" if relation else item.name,
                summary="\n".join(reference["quote"] for reference in refs),
                confidence=1.0, payload=payload, review_status=ReviewStatus.PENDING,
            )
            db.add(candidate)
            db.commit()
            with _replay_clock(annotation.available_at):
                reviewed = knowledge.resolve_review(
                    db, user_id=user_id, review_id=candidate.id, decision=ReviewResolve(action="confirm"),
                )
            formal[item.id] = reviewed.knowledge_id
    for change in sorted(fixture.changes, key=lambda item: item.effective_at):
        evidence = db.scalar(select(KnowledgeEvidence).where(
            KnowledgeEvidence.entity_id == formal[change.new],
            KnowledgeEvidence.project_id == project_id, KnowledgeEvidence.user_id == user_id,
            KnowledgeEvidence.start_line == change.evidence_line,
        ))
        proposal = evolution.create_change(
            db, user_id=user_id, project_id=project_id,
            proposal=ChangeCreate(new_entity_id=formal[change.new], old_entity_id=formal[change.old],
                                  evidence_id=evidence.id, kind="SUPERSEDES", reason=change.reason,
                                  effective_at=change.effective_at),
        )
        evolution.resolve_change(db, user_id=user_id, project_id=project_id, change_id=proposal.id, action="confirm")
    counts = {
        label: db.scalar(select(func.count()).select_from(model).where(model.project_id == project_id))
        for label, model in (
            ("sources", SourceDocument), ("chunks", SourceChunk), ("tasks", ProcessingTask),
            ("candidates", CandidateKnowledge), ("reviews", ReviewEvent), ("entities", KnowledgeEntity),
            ("relationships", KnowledgeRelationship), ("evidence", KnowledgeEvidence), ("changes", KnowledgeChange),
        )
    }
    snapshot = project_snapshot(db, user_id=user_id, project_id=project_id)
    return {"project_id": str(project_id), "repository_id": str(repository.id), "counts": counts, "snapshot": snapshot,
            "source_ids": source_ids, "knowledge_ids": {key: str(value) for key, value in formal.items()}}


def prepare_project(*, engine: Engine, dataset_root: Path, project_id: uuid.UUID,
                    settings: Settings, accept_curated_fixture: bool,
                    user_id: uuid.UUID = DEVELOPMENT_USER_ID) -> dict:
    if not accept_curated_fixture:
        raise PreparationError("Explicit --accept-curated-fixture is required to replay fixture review decisions")
    if settings.app_env not in {"development", "test", "evaluation"}:
        raise PreparationError("Fixture initialization is restricted to development/test/evaluation environments")
    fixture, summary, fingerprint = load_fixture(dataset_root)
    provenance = {"protocol": FIXTURE_PROTOCOL, "dataset": summary,
                  "fixture_id": fixture.fixture_id, "fixture_version": fixture.version,
                  "fixture_fingerprint_sha256": fingerprint, "accepted_curated_fixture": True,
                  "synthetic_history": True, "provider_call_count": 0}
    with engine.begin() as connection:
        if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
            # sqlite3 legacy transaction mode otherwise commits released savepoints.
            connection.exec_driver_sql("BEGIN")
        with Session(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as db:
            result = _populate(db, fixture=fixture, dataset_root=dataset_root,
                               project_id=project_id, user_id=user_id, settings=settings, provenance=provenance)
            # Reject an editor changing the corpus/annotations while it is loaded.
            if load_fixture(dataset_root)[2] != fingerprint:
                raise PreparationError("Fixture changed during initialization")
    return {"status": "succeeded", **provenance, **result}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--project-id", type=uuid.UUID, default=None, help="Unused UUID; an existing project is always refused")
    parser.add_argument("--output-dir", type=Path, help="New report directory; required unless --validate-only")
    parser.add_argument("--accept-curated-fixture", action="store_true", help="Accept versioned synthetic annotations and their replayed review decisions")
    parser.add_argument("--validate-only", action="store_true", help="Validate corpus/fixture/time consistency without database access")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = None
    try:
        fixture, summary, fingerprint = load_fixture(args.dataset.resolve())
        if args.validate_only:
            print(json.dumps({"dataset": summary, "fixture_id": fixture.fixture_id,
                              "fixture_fingerprint_sha256": fingerprint}, ensure_ascii=False, indent=2))
            return 0
        if not args.accept_curated_fixture:
            raise PreparationError("Explicit --accept-curated-fixture is required")
        if args.output_dir is None:
            raise PreparationError("--output-dir is required for initialization")
        args.output_dir.mkdir(parents=True, exist_ok=False)
        report = args.output_dir / "preparation.json"
        project_id = args.project_id or uuid.uuid4()
        report.write_text(json.dumps({"status": "preparing", "project_id": str(project_id)}) + "\n", encoding="utf-8")
        result = prepare_project(engine=configured_engine, dataset_root=args.dataset.resolve(),
                                 project_id=project_id, settings=get_settings(),
                                 accept_curated_fixture=True)
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        if report is not None:
            failure = {"status": "failed", "error_type": type(exc).__name__, "project_id": str(project_id)}
            if "result" in locals():
                failure.update(status="database_committed_report_failed", counts=result["counts"])
            try:
                report.write_text(json.dumps(failure) + "\n", encoding="utf-8")
            except OSError:
                pass
        if isinstance(exc, (DatasetError, PreparationError)):
            print(f"Evaluation preparation failed: {exc}", file=sys.stderr)
        elif isinstance(exc, AppError):
            print(f"Evaluation preparation failed with application error {exc.code}", file=sys.stderr)
        else:
            print(f"Evaluation preparation failed ({type(exc).__name__}); check local configuration without exposing credentials.", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
