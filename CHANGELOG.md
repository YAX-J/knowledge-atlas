# Changelog

All notable changes to Knowledge Atlas will be documented in this file.

The project is pre-release. Version numbers and release dates will be added when the first distributable milestone is defined.

## Unreleased

### Added

- Interactive Vue 3 Mock knowledge-graph frontend.
- Node search, selection, evidence expansion, relationship navigation, type filtering, temporal playback, and Mock questioning.
- Responsive desktop and mobile layouts.
- Architecture, frontend, knowledge-model, API, and roadmap documentation.
- Repository instructions, contribution guidance, setup documentation, ADR process, and GitHub templates.
- FastAPI backend foundation with CORS, request IDs, health endpoints, and standardized errors.
- Project creation/list/detail, Markdown upload, source preview, and task-status endpoints.
- SQLAlchemy models and an Alembic migration for projects, sources, processing tasks, and candidate knowledge.
- Docker Compose services for PostgreSQL/pgvector, Neo4j, and the API.
- Isolated backend API tests covering the first ingestion slice.
- Typed frontend API client functions while retaining Mock as the default data source.
- Explicit Markdown task execution, persistent heading/paragraph/list/code chunks, and paginated chunk APIs with stable UUIDs, exact text, heading paths, hashes, and source line locations.
- Identical-byte upload reuse within a user's project, idempotent completed tasks, failed-task retry, and atomic task claiming.
- Parsing/API regression tests, reversible chunk migration tests, and offline PostgreSQL migration compilation checks.
- API-backed frontend project/source workspace with project creation/pagination, Markdown upload, source preview, parsing/retry, chunk pagination, and loading/error/empty states.
- Paginated project-source listing with scoped latest-task references and interface tests.

### Changed

- Expanded the project README with current status, quick start, architecture, repository structure, and MVP definition.

### Known limitations

- Docker service connectivity has not been verified in the current environment because Docker is unavailable.
- Automatic task consumption, interrupted-task recovery, complete CommonMark parsing, extraction, graph projection, retrieval, and real Agent responses are not implemented.
- Graph and question views remain Mock; real question history, routing, and persisted view preferences are not implemented.
