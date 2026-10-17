# Knowledge Atlas Implementation Plan

[简体中文](PLANS.zh-CN.md)

This file identifies the active implementation phase and points to the detailed roadmap. It does not replace `docs/ROADMAP.md`.

## Current state

Completed:

- Repository purpose and graduation-project scope defined.
- Interactive Vue Mock frontend implemented.
- Desktop and mobile knowledge-graph workflows verified.
- Architecture, knowledge model, API draft, and development roadmap documented.
- Repository collaboration and decision-recording files initialized.
- FastAPI application, health endpoints, error envelope, and request IDs implemented.
- Project, Markdown source, and queued-task APIs implemented.
- PostgreSQL-oriented models, initial Alembic migration, and local service composition added.
- Backend interface tests implemented with an isolated SQLite database.
- Typed frontend API client foundation added while Mock remains the default.
- Explicit Markdown parsing tasks, persistent line-addressable chunks, and chunk pagination implemented.
- Identical-byte upload reuse, deterministic chunk IDs, idempotent task execution, and failed-task retry implemented.
- Frontend project creation/listing, source listing/upload, parsing/retry, source preview, and paginated evidence chunks integrated with real APIs while preserving the Mock graph.
- Optional database-backed parsing worker, leased execution, stale-result fencing, interrupted-task recovery, and bounded automatic attempts implemented.

## Active phase

The active phase is schema-constrained extraction and human review. The user reports the native PostgreSQL 17/pgvector ingestion path, duplicate reuse, restart persistence, and automatic parsing passed. PostgreSQL contention and lease-recovery fault injection remain separate outstanding checks.

Implemented in this slice:

- Explicit DeepSeek extraction from parsed source chunks, with strict JSON/type/endpoint and exact-evidence validation.
- Atomic pending candidates, reusable successful extraction tasks, manual retries and expired-lease recovery.
- Source-scoped candidate UI and paginated review APIs, name/summary edits, confirm/reject, and decision audit records.

Acceptance still needed:

- Configure a local DeepSeek key and verify a real model response against a short public Markdown note.
- Review evidence quality and model output on representative inputs; simulated tests do not establish real extraction quality.
- Retain PostgreSQL concurrency/recovery validation as a tracked integration check.

Formal graph entities/relationships, promotion of confirmed candidates, merging/disambiguation, retrieval, and Agent answers remain future work. A confirmed candidate is not yet a formal graph object. Neo4j remains deferred under ADR 0005. See [ADR 0006](docs/adr/0006-deepseek-candidate-review.md) for this slice's boundaries.

## Later phases

1. Markdown parsing, chunking, and source locations.
2. Schema-constrained knowledge extraction and human confirmation.
3. PostgreSQL graph persistence and real frontend data.
4. Keyword, vector, and graph hybrid retrieval.
5. Evidence-grounded Agent answers.
6. Code and GitHub ingestion.
7. Temporal evolution, governance, experiments, and deployment.

Detailed deliverables, risks, and twelve-week scheduling are maintained in `docs/ROADMAP.md`.

## Planning rules

- Work on one bounded phase at a time.
- Confirm architecture-impacting choices with an ADR.
- Keep acceptance criteria observable and testable.
- Update this file when the active phase changes, not after every small task.
- Do not mark a phase complete only because documentation or scaffolding exists.
