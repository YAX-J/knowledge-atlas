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

### Changed

- Expanded the project README with current status, quick start, architecture, repository structure, and MVP definition.

### Known limitations

- Docker service connectivity has not been verified in the current environment because Docker is unavailable.
- Markdown parsing, extraction, graph projection, retrieval, and real Agent responses are not implemented.
- Project, source, and question navigation entries are placeholders in the current frontend.
