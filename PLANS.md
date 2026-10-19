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
- Explainable hybrid retrieval with fixed keyword/vector/one-hop graph weights, bounded candidates, visible-relationship filtering, and per-hit score composition.
- Synchronous evidence-grounded questions with bounded hybrid retrieval, strict DeepSeek output, application-validated citation UUIDs, and a real frontend workspace.
- Local UTF-8 Java source upload with deterministic `code`/`comment`/`type`/`method` chunks, exact source lines, and reuse of the existing parsing worker and evidence pipeline.
- Separate desktop single-file and folder-upload entry points; folders contribute up to 50 supported Markdown/Java files, uploaded sequentially with persisted relative paths, per-file deduplication, and partial-success retention.

## Active phase

The active phase is Stage 4 code ingestion. Its bounded local-file slice accepts Java files, uses `code_parsing`, preserves exact source lines in structural chunks, persists optional folder-relative paths, and reuses the existing worker and evidence workflow. It does not claim a complete Java AST, symbol graph, call graph, GitHub import, or incremental repository synchronization. See [ADR 0012](docs/adr/0012-bounded-java-source-ingestion.md).

Implemented in this slice:

- `.java` upload validation and `source_type=java`, with source type included in duplicate-reuse semantics.
- A deterministic local parser for top-level types and conventional direct-member methods, including comment/string/text-block shielding while retaining exact chunk text.
- Stable one-based inclusive line ranges, hashes, structure paths, and chunk UUIDs for `code`, `comment`, `type`, and `method` chunks, with type annotations grouped into the type.
- `code_parsing` support in manual execution and the leased database worker.
- Desktop source-workspace upload, MD/JAVA labels, and Java chunk-kind display.
- A bounded source-structure endpoint and desktop outline for stable type/field/method symbols plus same-file unqualified/`this.` call hints, kept outside the formal graph.
- Separate desktop single-file and folder upload; folders ignore unsupported/empty files and import up to 50 Markdown/Java sources while persisting normalized relative paths. Failures are reported per file without rolling back successful uploads.

Acceptance still needed:

- Manually upload and parse representative Java files, including comments, string literals, text blocks, multiple top-level types, constructors, methods, and syntax the bounded parser intentionally leaves as type/code text.
- Configure a local DeepSeek key and verify a real model response against a short public Markdown note.
- Review evidence quality and model output on representative inputs; simulated tests do not establish real extraction quality.
- Verify the real project graph against native PostgreSQL in a browser, including empty, truncated, filtered, and time-filtered states.
- Retain PostgreSQL Worker/API concurrency and recovery validation; review/promotion repeated-confirmation contention has passed in a disposable schema.
- Evaluate semantic and hybrid ranking on representative native-PostgreSQL data with confirmed relationships; the current real-provider smoke project has seven indexed entities but no confirmed edges.

Project keyword, semantic-vector, explainable one-hop graph hybrid retrieval, and first-pass evidence-grounded answers are implemented. Entity disambiguation, question history, multi-turn Agent behavior, and streaming remain future work. See [ADR 0011](docs/adr/0011-synchronous-evidence-grounded-questions.md).

## Later phases

1. Representative real-answer acceptance and retrieval/prompt quality evaluation.
2. Add repository identity and cross-file Java resolution, then GitHub ingestion and incremental synchronization.
3. Temporal evolution, governance, experiments, and deployment.

Markdown parsing, schema-constrained review, and confirmed-candidate graph persistence are complete as bounded slices.

Detailed deliverables, risks, and twelve-week scheduling are maintained in `docs/ROADMAP.md`.

## Planning rules

- Work on one bounded phase at a time.
- Confirm architecture-impacting choices with an ADR.
- Keep acceptance criteria observable and testable.
- Update this file when the active phase changes, not after every small task.
- Do not mark a phase complete only because documentation or scaffolding exists.
