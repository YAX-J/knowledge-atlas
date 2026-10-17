# Knowledge Atlas Backend

FastAPI service for the first Knowledge Atlas persistence and Markdown-ingestion slice.

## Implemented behavior

- Liveness and PostgreSQL/Neo4j readiness endpoints.
- Request IDs, CORS, request logging, and a stable error envelope.
- Create, list, and retrieve projects within a development-user boundary.
- Validate and store UTF-8 Markdown with a SHA-256 content hash.
- Create and query a queued processing task for each accepted upload.
- Persist project, source, task, and candidate-knowledge records.

Parsing, model extraction, Neo4j projection, search, and Agent answers are not implemented yet.

## Setup

```bash
python -m venv .venv
# Activate the virtual environment for the current shell.
python -m pip install -e ".[dev]"
```

Copy `.env.example` to `.env`. From the repository root, start PostgreSQL and Neo4j:

```bash
docker compose up -d postgres neo4j
```

Then apply the schema and start the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

OpenAPI documentation is available at `http://localhost:8000/docs`.

## Test

```bash
python -m pytest
```

Tests use an isolated SQLite database. Run `/api/v1/health/ready` against the Docker environment to verify the real PostgreSQL and Neo4j connections.

## Structure

```text
app/
├─ api/          # Versioned HTTP routes and dependencies
├─ core/         # Settings, errors, logging, and middleware
├─ db/           # SQLAlchemy base and session factory
├─ models/       # Authoritative persistence models
├─ schemas/      # API request and response models
└─ services/     # Persistence workflows and domain validation
migrations/      # Alembic environment and revisions
tests/           # API behavior tests
```

