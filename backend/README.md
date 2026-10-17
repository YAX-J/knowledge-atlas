# Knowledge Atlas Backend

[简体中文](README.zh-CN.md)

FastAPI service for the first Knowledge Atlas persistence and Markdown-ingestion slice.

## Implemented behavior

- Liveness and PostgreSQL/Neo4j readiness endpoints.
- Request IDs, CORS, request logging, and a stable error envelope.
- Create, list, and retrieve projects within a development-user boundary.
- Paginate a project's source metadata and latest tasks within the same user/project boundary.
- Validate and store UTF-8 Markdown with a SHA-256 content hash.
- Create/query parsing tasks and explicitly run them through the API.
- Automatically consume queued parsing tasks in an optional independent worker process, with leased claims, interrupted-task recovery, and fenced result writes.
- Persist headings, paragraphs, lists, and fenced code with exact text, heading paths, hashes, and one-based inclusive line ranges.
- Reuse the original source/task on identical-byte uploads within a user's project, even if the filename changes.
- Paginate stored chunks and safely repeat completed tasks or retry failed tasks.
- Persist project, source, task, and candidate-knowledge records.

Model extraction, Neo4j projection, search, and Agent answers are not implemented yet.

## Setup

```bash
python -m venv .venv
# Activate the virtual environment for the current shell.
python -m pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and set `DATABASE_URL`, `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD` to your native local service settings. The example credentials are development placeholders, not your existing database credentials. API and worker must use the same environment file from `backend/`.

Start your locally installed PostgreSQL and Neo4j, and create a dedicated `knowledge_atlas` database (or configure another database name). PostgreSQL must have pgvector installed: the initial migration runs `CREATE EXTENSION IF NOT EXISTS vector`, so the account needs permission or an administrator must enable it in the target database first. Docker is not required.

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

The parser supports a structural subset: ATX/Setext headings, paragraphs, lists, and fenced code. Other syntax is retained as text. Chunk IDs remain stable for the same source and boundaries. Changed file bytes create a separate source rather than updating an existing source. PostgreSQL project locks serialize duplicate upload creation; SQLite does not validate those locking guarantees. The manual endpoint runs parsing in the API process; automatic execution uses the worker described below. A complete CommonMark AST is not implemented.

## Automatic parsing worker

Apply the latest migration first. In another terminal with the backend virtual environment activated, run:

```bash
python -m app.worker
```

The worker polls queued tasks and expired running tasks within the development user's active projects. It shares the parser and persistence workflow with the API. Upload responses remain HTTP 202 with task IDs; refresh task/source state in the UI to view the result. No browser polling or automatic retry of ordinary failed tasks is added.

For a single pass:

```bash
python -m app.worker --once
```

`--once` handles at most one task. Exit code 0 means a task succeeded or no work was available; 1 means processing, recovery-limit handling, or an infrastructure operation failed. `--user-id <uuid>` explicitly scopes the trusted local worker to another user; the default is the same temporary development UUID as the API.

| Environment variable | Default | Behavior |
| --- | --- | --- |
| `TASK_LEASE_SECONDS` | `300` | Fixed execution lease, 1–86400 seconds; use the same value for API and worker |
| `TASK_MAX_ATTEMPTS` | `3` | Recovery stops an expired task at this total attempt count, 1–100 |
| `WORKER_POLL_INTERVAL_SECONDS` | `2` | Wait between idle/error iterations, greater than 0 and at most 60 |

Each claim gets a fresh internal execution UUID, an incremented attempt count, and an expiry time. If a process is killed, another worker can claim the task after expiry. Legacy running tasks without a lease use their start time (or last update time when absent) as the timeout baseline. Reaching the attempt limit marks the task/source failed with `TASK_ATTEMPTS_EXHAUSTED`; explicit manual retries remain possible beyond the count. Normal parsing failures stay failed for manual retry.

Both success and failure updates require the current execution UUID and running status. Chunks, source state, and final task state commit atomically. A replaced process cannot overwrite the current result even if it resumes later. Leases have no heartbeat: a live parser exceeding its lease can overlap a replacement in computation, so size the lease above normal parsing duration. SIGINT/SIGTERM request exit after the current iteration; forced termination relies on lease recovery.

Docker Compose is an optional alternative: from the repository root, `docker compose up -d --build` also starts the worker. It waits for the API's liveness check after migrations, uses the same backend image, and has no HTTP port. Default acceptance uses native local PostgreSQL/Neo4j; real connectivity and PostgreSQL contention/recovery remain to be validated. Optional container startup has not been verified.

## Test

```bash
python -m pytest
```

Tests use isolated SQLite databases and cover parsing, API behavior, failure/retry, access isolation, migration upgrade/downgrade with legacy running tasks, offline PostgreSQL SQL compilation, worker recovery/fencing across independent sessions, and actual one-shot worker subprocesses. Run `/api/v1/health/ready` against your configured native local services to verify the real PostgreSQL and Neo4j connections. Both dependencies must report `up` for acceptance. Offline compilation is not a live database integration test.

## Structure

```text
app/
├─ worker.py     # Independent database-backed parsing consumer
├─ api/          # Versioned HTTP routes and dependencies
├─ core/         # Settings, errors, logging, and middleware
├─ db/           # SQLAlchemy base and session factory
├─ models/       # Authoritative persistence models
├─ schemas/      # API request and response models
└─ services/     # Persistence workflows and domain validation
migrations/      # Alembic environment and revisions
tests/           # API behavior tests
```

