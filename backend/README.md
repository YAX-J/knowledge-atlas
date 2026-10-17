# Knowledge Atlas Backend

FastAPI service for the first Knowledge Atlas persistence and Markdown-ingestion slice.

## Implemented behavior

- Liveness and PostgreSQL/Neo4j readiness endpoints.
- Request IDs, CORS, request logging, and a stable error envelope.
- Create, list, and retrieve projects within a development-user boundary.
- Paginate a project's source metadata and latest tasks within the same user/project boundary.
- Validate and store UTF-8 Markdown with a SHA-256 content hash.
- Create/query parsing tasks and explicitly run them through the API.
- Persist headings, paragraphs, lists, and fenced code with exact text, heading paths, hashes, and one-based inclusive line ranges.
- Reuse the original source/task on identical-byte uploads within a user's project, even if the filename changes.
- Paginate stored chunks and safely repeat completed tasks or retry failed tasks.
- Persist project, source, task, and candidate-knowledge records.

Automatic task consumption, model extraction, Neo4j projection, search, and Agent answers are not implemented yet.

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

## Exercise the parsing flow

Use the interactive API documentation in this order:

1. `POST /api/v1/projects` to create a project.
2. `POST /api/v1/projects/{project_id}/sources` to upload a UTF-8 `.md` or `.markdown` file.
3. `POST /api/v1/tasks/{task_id}/run` to synchronously execute parsing.
4. `GET /api/v1/tasks/{task_id}` to inspect status and error information.
5. `GET /api/v1/sources/{source_id}/chunks?page=1&page_size=20` to inspect evidence text and line locations.

`GET /api/v1/projects/{project_id}/sources` restores the source list and each source's latest task after a frontend refresh. It excludes original content; use the source-detail endpoint for preview text.

New tasks use type `markdown_parsing`; legacy queued `knowledge_extraction` uploads can also run parsing only. Successful tasks end at `succeeded`/`parsed`/100 and sources become `ready`. This does not mean knowledge extraction has run. Execution failures return HTTP 200 with a `failed` task and a sanitized error; the same endpoint retries failed tasks. Repeating a succeeded task returns the existing result, while running/cancelled tasks return HTTP 409. Re-upload responses contain the reused task's current status, which need not be `queued`.

The parser supports a structural subset: ATX/Setext headings, paragraphs, lists, and fenced code. Other syntax is retained as text. Chunk IDs remain stable for the same source and boundaries. Changed file bytes create a separate source rather than updating an existing source. PostgreSQL project locks serialize duplicate upload creation; SQLite does not validate those locking guarantees. Requests run parsing in the API process: there is no queue consumer, timeout recovery for an interrupted running task, or complete CommonMark AST yet.

## Test

```bash
python -m pytest
```

Tests use isolated SQLite databases and cover parsing, API behavior, failure/retry, access isolation, migration upgrade/downgrade, and offline PostgreSQL SQL compilation. Run `/api/v1/health/ready` against the Docker environment to verify the real PostgreSQL and Neo4j connections. Offline compilation is not a live database integration test.

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

