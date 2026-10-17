# Changelog

[简体中文](CHANGELOG.zh-CN.md)

All notable changes to Knowledge Atlas will be documented in this file.

The project is pre-release. Version numbers and release dates will be added when the first distributable milestone is defined.

## Unreleased

### Added

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

- Removed the Neo4j driver, settings, readiness checks, and optional Compose service/volume declarations. PostgreSQL is the sole current database and stores the formal graph; Neo4j is deferred under ADR 0005. Readiness now reports only PostgreSQL and still returns HTTP 503 for a failed database connection.
- Native local PostgreSQL/pgvector are the default development and acceptance path; setup guides and plans now treat Docker Compose as optional and document actual local connection settings.
- Expanded the project README with current status, quick start, architecture, repository structure, and MVP definition.

### Known limitations

- The user reports PostgreSQL 17/pgvector startup, upload/parsing, duplicate reuse, restart persistence, and automatic parsing passed. PostgreSQL contention and lease-recovery fault injection remain unverified. Optional Docker startup has not been verified either.
- Worker leases are fixed without heartbeats or preemptive cancellation.
- Complete CommonMark parsing, entity disambiguation, retrieval, and real Agent responses are not implemented. Real DeepSeek calls remain unverified; tests and browser checks use simulated model responses. PostgreSQL 17.10 disposable-schema checks passed graph migrations, evidence reads, and concurrent identical confirmations; native-database browser acceptance and real-data graph quality remain unverified.
- The demo graph and question view remain Mock; the project graph uses real API data. Real question history, routing, and persisted view preferences are not implemented.
