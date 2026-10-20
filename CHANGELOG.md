# Changelog

[简体中文](CHANGELOG.zh-CN.md)

All notable changes to Knowledge Atlas will be documented in this file.

The project is pre-release. Version numbers and release dates will be added when the first distributable milestone is defined.

## Unreleased

### Added

- Explicit bounded GitHub snapshot synchronization from a repository default branch or requested ref, with optional backend-only token authentication, deterministic selection of up to 50 Markdown/Java blobs, a 20 MiB aggregate budget, per-file import/reuse/skip results, existing parsing-task reuse, and desktop controls.
- Bounded repository-scoped Java cross-file method-call hints for direct type-qualified and current-type field receivers, with package/import resolution, stable target IDs, exact source paths and lines, overload ambiguity, truncation, and desktop outline presentation outside the formal graph.
- Normalized project-scoped GitHub remote registration for HTTPS, SCP-style SSH, and `ssh://` forms, with optional linking to local-folder repositories, remote-only identities, conflict isolation, a repository list UI, and a reversible migration. Registration does not contact GitHub or import repository content.
- Project-scoped local-folder repository identities with idempotent resolve/list APIs, nullable source membership, repository-relative paths, repository-aware duplicate reuse, repository labels in source views, and repository-bounded Java type resolution. Existing sources remain unassigned without backfill.
- Bounded repository-scoped Java type resolution in the source-structure view. Ready sources expose cross-file top-level `extends`/`implements` targets through explicit imports, same-package lookup, and wildcard imports, including target paths, source lines, ambiguity, and truncation without writing derived data to the formal graph.
- Separate desktop single-file and folder-upload entry points. Folder selection ignores unsupported/empty files, imports up to 50 Markdown/Java sources through the existing sequential upload contract, persists normalized relative paths, shows them in source/evidence views, and retains successful uploads when another file fails.
- A bounded read-only Java source-structure endpoint and desktop outline with stable type/field/method symbols, source lines, and same-file unqualified/`this.` call hints. Derived relationships remain separate from reviewed formal knowledge and report overload collisions as ambiguous.
- Bounded local Java source ingestion with `.java` upload validation, `code_parsing` tasks, leased-worker support, exact line-preserving `code`/`comment`/`type`/`method` chunks, stable structure paths/UUIDs, type-level annotation grouping, and desktop MD/JAVA source presentation. Complete ASTs, call graphs, GitHub import, and incremental repository sync remain out of scope.
- Synchronous, non-persistent evidence-grounded questions with bounded hybrid retrieval, strict DeepSeek JSON output, application-validated citation UUIDs, deterministic no-evidence refusal, retrieval summaries, and a responsive real frontend workspace with source-line and entity navigation.
- Explainable `hybrid` project search with fixed keyword/vector/one-hop graph weights, bounded visible-relationship expansion, normalized score components, relationship explanations, stable ranking, and frontend mode switching.
- Explicit formal-entity semantic indexing with a configurable OpenAI-compatible Embeddings service, 1024-dimensional pgvector storage, content-hash reuse, exact cosine retrieval, index coverage counts, and frontend keyword/vector mode switching.
- Evidence-backed project keyword search over confirmed entity names, summaries, and quotes, with deterministic ranking, type/time filters, literal wildcard handling, bounded results, and detail/neighborhood navigation. No migration or model call is required.

- Repository-local agent skills under `.agents/skills/` for extraction, review/promotion, migrations, verification, ingestion, frontend, and bilingual documentation workflows, indexed from `AGENTS.md`.
- Confirmation now promotes candidates into scoped PostgreSQL entities, relationships, and evidence in the same transaction as review state and audit events, including idempotent UUIDs, endpoint promotion, and legacy-confirmation replay. Read-only project graph and entity/relationship detail APIs expose time-filtered, bounded views without canvas coordinates.
- Explicit DeepSeek JSON candidate extraction with constrained types/endpoints, exact source-quote validation, atomic candidate persistence, reusable successful tasks, manual retry/expired-lease recovery, and fenced writes.
- Source-scoped candidate UI and paginated review APIs with confirm/reject, name/summary edits, endpoint confirmation rules, and reversible review-event migration. Model calls are not triggered by the parsing worker.

- Simplified Chinese companions for repository guidance, plans, contribution/security policies, changelog, backend/setup instructions, and ADR guidance/records, with reciprocal language links and a Chinese README index.
- Optional database-backed parsing worker with continuous/one-shot modes, scoped task polling, execution leases, stale-result fencing, interrupted-task recovery, and bounded automatic attempts.
- Reversible lease migration preserving historical tasks, shared development identity, worker configuration, and a Compose worker gated on API liveness after migrations.
- Worker tests for recovery, stale success/failure writes across independent sessions, boundary isolation, attempt limits, and actual one-shot subprocess success/failure.

- Interactive Vue 3 Mock knowledge-graph frontend.
- Node search, selection, evidence expansion, relationship navigation, type filtering, temporal playback, and Mock questioning.
- Responsive desktop and mobile layouts.
- Architecture, frontend, knowledge-model, API, and roadmap documentation.
- Repository instructions, contribution guidance, setup documentation, ADR process, and GitHub templates.
- FastAPI backend foundation with CORS, request IDs, health endpoints, and standardized errors.
- Project creation/list/detail, Markdown upload, source preview, and task-status endpoints.
- SQLAlchemy models and an Alembic migration for projects, sources, processing tasks, and candidate knowledge.
- Docker Compose services for PostgreSQL/pgvector and the API.
- Isolated backend API tests covering the first ingestion slice.
- Typed frontend API client functions while retaining Mock as the default data source.
- Explicit Markdown task execution, persistent heading/paragraph/list/code chunks, and paginated chunk APIs with stable UUIDs, exact text, heading paths, hashes, and source line locations.
- Identical-byte upload reuse within a user's project, idempotent completed tasks, failed-task retry, and atomic task claiming.
- Parsing/API regression tests, reversible chunk migration tests, and offline PostgreSQL migration compilation checks.
- API-backed frontend project/source workspace with project creation/pagination, Markdown upload, source preview, parsing/retry, chunk pagination, and loading/error/empty states.
- Paginated project-source listing with scoped latest-task references and interface tests.

### Changed

- Candidate review lists now place entities before relationships deterministically, preventing relation actions from appearing before their required endpoints.
- Removed the Neo4j driver, settings, readiness checks, and optional Compose service/volume declarations. PostgreSQL is the sole current database and stores the formal graph; Neo4j is deferred under ADR 0005. Readiness now reports only PostgreSQL and still returns HTTP 503 for a failed database connection.
- Native local PostgreSQL/pgvector are the default development and acceptance path; setup guides and plans now treat Docker Compose as optional and document actual local connection settings.
- Expanded the project README with current status, quick start, architecture, repository structure, and MVP definition.

### Known limitations

- The user reports PostgreSQL 17/pgvector startup, upload/parsing, duplicate reuse, restart persistence, and automatic parsing passed. PostgreSQL contention and lease-recovery fault injection remain unverified. Optional Docker startup has not been verified either.
- Worker leases are fixed without heartbeats or preemptive cancellation.
- Complete CommonMark parsing, entity disambiguation, retrieval-weight tuning, and multi-turn Agent behavior are not implemented. Real DeepSeek answer quality and representative native-pgvector hybrid quality with confirmed relationships remain unverified; automated tests cover nonzero graph fusion, while a seven-entity real-provider search smoke passed without relationships.
- The independent evidence-question workspace uses the real API, while demo-graph follow-up remains Mock. Question history, streaming, routing, and persisted view preferences are not implemented.
