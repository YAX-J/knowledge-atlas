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
- Explicit DeepSeek extraction with evidence validation, audited review, and promotion of confirmed candidates into scoped PostgreSQL entities, relationships, and evidence.
- Read-only project graph, entity-detail, and relationship-detail APIs with user/project/time scoping and node/edge limits, plus a real project-graph frontend page.
- Evidence-backed project keyword search over formal entity names, summaries, and quotes, with ranking, type/time filters, bounded results, and graph/detail navigation.
- Explicit 1024-dimensional formal-entity semantic indexing, pgvector cosine retrieval, content-hash reuse, and frontend keyword/vector mode switching.

## Active phase

The active slice is the two-lane keyword and semantic-vector retrieval baseline. Migration head is `20261018_0006`; APIs, SQLite simulated-vector tests, PostgreSQL offline SQL, and the frontend build are verified. Real embedding-provider and native pgvector retrieval acceptance, Worker/API contention, lease recovery, native-database browser acceptance, and real DeepSeek acceptance remain outstanding.

Implemented in this slice:

- Scoped, read-only keyword matching of formal entity names, summaries, and evidence; all terms must match and SQL wildcards stay literal.
- Reproducible field-weight ranking, stable tie order, type/time filters, bounded hits, and evidence excerpts.
- Project-graph search form with empty/error/retry/clear states and selection into entity details or neighborhoods.
- Independent request counters for search results across project changes and clearing; demo-header search remains separate.
- Backend tests, frontend build, isolated browser checks, and native PostgreSQL SQL validation.
- Explicit semantic-index rebuild, model/content-hash reuse, 1024-dimension validation, exact pgvector cosine retrieval, and frontend mode switching.

Acceptance still needed:

- Configure a local DeepSeek key and verify a real model response against a short public Markdown note.
- Review evidence quality and model output on representative inputs; simulated tests do not establish real extraction quality.
- Verify the real project graph against native PostgreSQL in a browser, including empty, truncated, filtered, and time-filtered states.
- Retain PostgreSQL Worker/API concurrency and recovery validation; review/promotion repeated-confirmation contention has passed in a disposable schema.
- Configure a real OpenAI-compatible embedding provider and validate the 1024-dimensional index and semantic ranking on native PostgreSQL.

Project keyword and semantic-vector retrieval with evidence are implemented. Entity disambiguation, hybrid ranking, and Agent answers remain future work. Confirmed candidates promote to formal graph objects; the demo graph and question view remain Mock. See [ADR 0009](docs/adr/0009-explicit-semantic-index.md) for the semantic boundary.

## Later phases

1. Fuse keyword, vector, and graph-relation scores.
2. Evidence-grounded Agent answers.
3. Code and GitHub ingestion.
4. Temporal evolution, governance, experiments, and deployment.

Markdown parsing, schema-constrained review, and confirmed-candidate graph persistence are complete as bounded slices.

Detailed deliverables, risks, and twelve-week scheduling are maintained in `docs/ROADMAP.md`.

## Planning rules

- Work on one bounded phase at a time.
- Confirm architecture-impacting choices with an ADR.
- Keep acceptance criteria observable and testable.
- Update this file when the active phase changes, not after every small task.
- Do not mark a phase complete only because documentation or scaffolding exists.
