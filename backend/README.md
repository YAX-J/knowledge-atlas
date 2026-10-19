# Knowledge Atlas Backend

[简体中文](README.zh-CN.md)

FastAPI service for Knowledge Atlas persistence, Markdown/Java ingestion, evidence-validated candidate extraction/review, and bounded read-only project-graph queries.

## Implemented behavior

- Liveness and PostgreSQL readiness endpoints.
- Request IDs, CORS, request logging, and a stable error envelope.
- Create, list, and retrieve projects within a development-user boundary.
- Resolve and list project-scoped local-folder repository identities, and paginate source metadata/latest tasks within the same user/project boundary.
- Validate and store UTF-8 Markdown and Java source with a SHA-256 content hash, optional repository identity, and normalized repository-relative path.
- Create/query parsing tasks and explicitly run them through the API.
- Automatically consume queued parsing tasks in an optional independent worker process, with leased claims, interrupted-task recovery, and fenced result writes.
- Persist Markdown headings/paragraphs/lists/fenced code and Java code/comment/type/method chunks with exact text, structure paths, hashes, and one-based inclusive line ranges. Top-level type annotations stay with the type; comment-only lines outside methods are separate comment chunks.
- Reuse the original source/task on identical-byte uploads within a user's project, nullable repository, and source type, even if the filename changes.
- Paginate stored chunks and safely repeat completed tasks or retry failed tasks.
- Derive a bounded read-only Java outline with stable type/field/method symbols, unqualified or `this.` same-file call hints, and repository-scoped cross-file `extends`/`implements` targets resolved from packages and imports; derived structure is not promoted into the formal graph.
- Persist project, source, task, and candidate-knowledge records.
- Promote confirmed candidates into scoped PostgreSQL entities, relationships, and evidence within the review transaction, with stable UUIDs, endpoint promotion, idempotent repeats, and legacy-confirmation replay.
- Serve read-only project graph, entity-detail, and relationship-detail views with user/project/time scoping, node/edge limits, and server-calculated evidence lines.

Explicit DeepSeek extraction, review, formal graph promotion, project keyword/vector/one-hop graph hybrid retrieval, and synchronous evidence-grounded questions are implemented. The semantic index uses an explicit rebuild operation and a configurable OpenAI-compatible Embeddings service. A real-provider/native-pgvector search smoke has passed; representative graph-bearing retrieval and real answer quality remain outstanding. Entity disambiguation, persistent history, and multi-turn Agent behavior are not implemented.

## Setup

```bash
python -m venv .venv
# Activate the virtual environment for the current shell.
python -m pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and set `DATABASE_URL` to your native local service settings. The example credentials are development placeholders, not your existing database credentials. API and worker must use the same environment file from `backend/`.

Start your locally installed PostgreSQL, and create a dedicated `knowledge_atlas` database (or configure another database name). PostgreSQL must have pgvector installed: the initial migration runs `CREATE EXTENSION IF NOT EXISTS vector`, so the account needs permission or an administrator must enable it in the target database first. Docker is not required.

Then apply the schema and start the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

OpenAPI documentation is available at `http://localhost:8000/docs`.

## Exercise the parsing flow

Use the interactive API documentation in this order:

1. `POST /api/v1/projects` to create a project.
2. For a folder, call `POST /api/v1/projects/{project_id}/repositories/resolve` with its root name, then upload each UTF-8 `.md`, `.markdown`, or `.java` file through `POST /api/v1/projects/{project_id}/sources` with `repository_id` and a normalized repository-relative `relative_path`. Single-file uploads omit both fields.
3. `POST /api/v1/tasks/{task_id}/run` to synchronously execute parsing.
4. `GET /api/v1/tasks/{task_id}` to inspect status and error information.
5. `GET /api/v1/sources/{source_id}/chunks?page=1&page_size=20` to inspect evidence text and line locations.

`GET /api/v1/projects/{project_id}/sources` restores the source list and each source's latest task after a frontend refresh. It includes nullable repository ID/name and `relative_path` metadata but excludes original content; use the source-detail endpoint for preview text. Identical-byte reuse retains the first source's filename and relative path within the same nullable repository.

Markdown tasks use `markdown_parsing`, Java tasks use `code_parsing`, and legacy queued `knowledge_extraction` uploads can run Markdown parsing only. Successful tasks end at `succeeded`/`parsed`/100 and sources become `ready`. This does not mean knowledge extraction has run. Execution failures return HTTP 200 with a `failed` task and a sanitized error; the same endpoint retries failed tasks. Repeating a succeeded task returns the existing result, while running/cancelled tasks return HTTP 409. Re-upload responses contain the reused task's current status, which need not be `queued`.

The Markdown parser supports ATX/Setext headings, paragraphs, lists, and fenced code. The bounded Java parser identifies top-level types and conventional direct-member methods, while retaining all source text. The source-structure view also resolves repository-local top-level `extends`/`implements` targets through explicit imports, same-package lookup, and wildcard imports across at most 100 ready Java sources; legacy unassigned sources resolve only against other unassigned sources. Chunk IDs remain stable for the same source and boundaries. Changed bytes create a separate source rather than updating an existing source. PostgreSQL project locks serialize repository resolution and duplicate upload creation; SQLite does not validate those locking guarantees. The manual endpoint runs parsing in the API process; automatic execution uses the worker described below. Complete CommonMark/Java ASTs, cross-file Java method calls, Git remote identity, GitHub import, and incremental repository sync are not implemented.

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

Docker Compose is an optional alternative: from the repository root, `docker compose up -d --build` also starts the worker. It waits for the API's liveness check after migrations, uses the same backend image, and has no HTTP port. Default acceptance uses native local PostgreSQL; the user reports native PostgreSQL 17/pgvector startup, ingestion, duplicate reuse, restart persistence, and automatic parsing passed; PostgreSQL contention/recovery fault injection remains unverified. Optional container startup has not been verified.

## DeepSeek candidate extraction and review

Apply `alembic upgrade head` (expected `20261019_0008`) before review or semantic-index operations. Configure only the backend `.env`:

```dotenv
DEEPSEEK_API_KEY=your_local_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_TIMEOUT_SECONDS=120
EXTRACTION_MAX_INPUT_CHARS=60000
EMBEDDING_API_KEY=your_embedding_key
EMBEDDING_BASE_URL=https://your-provider.example/v1
EMBEDDING_MODEL=your-1024-dimension-model
EMBEDDING_DIMENSIONS=1024
```

The default model follows the [DeepSeek API documentation](https://api-docs.deepseek.com/). The adapter uses JSON output and non-thinking mode; schema validation still happens locally. Restart the API after configuration changes. The local environment file already has empty/default fields where absent; keep actual secrets out of Git and browser configuration.

After parsing a source, open its candidate section and explicitly request extraction. This sends that source's chunks to DeepSeek. `POST /api/v1/sources/{source_id}/extract` executes synchronously; `GET /api/v1/sources/{source_id}/extraction` reads task state. The parsing worker never initiates model calls. Limits are 100 chunks and 60000 characters in serialized input JSON by default, 50 entities, 100 relationships, 8192 output tokens, and a 1 MiB response. Oversized input is rejected, not silently truncated; split it into smaller sources.

Outputs must match the schema, reference only extracted entities, and quote exact text from same-source chunks. A whole batch is accepted or rejected. Successful extraction is reused per source/prompt version, including after model-setting changes; this version has no forced re-extraction. Failed calls require explicit retry. Interrupted calls can be retried after their lease expires (at least the configured task lease or model timeout plus 60 seconds); stale executions cannot overwrite a replacement. No automatic retry is made because it could repeat model charges. A timed-out/interrupted call may already have reached the provider.

Review candidates through `GET /api/v1/projects/{project_id}/reviews` and `POST /api/v1/reviews/{review_id}/resolve`. Confirm or reject, optionally editing name/summary before confirmation. Relationships require confirmed endpoint entities. Repeating the same decision is idempotent; changed decisions, merge, undo, and re-extraction are not supported. Migration `0004` adds audit records with actor, time, and before/after values. Migration `0005` adds formal graph tables; downgrading it removes graph records and evidence while preserving sources, candidates, and review events.

Confirmation writes formal entities, relationships, and evidence in the review transaction. Semantic vectors are generated later by an explicit index operation and cannot fail confirmation. Entity merging and disambiguation remain future work; real DeepSeek answer quality and embedding providers require separate acceptance.

## Project graph

`GET /api/v1/projects/{project_id}/graph` returns `nodes`, `edges`, and `truncated` for active, user-scoped projects. Optional parameters are `center_id`, `depth` (1 or 2), `types` (comma-separated entity types), `valid_at`, and `limit` (1–200, default 100); edges are capped at 500. Visibility requires `status != archived`, `valid_from <= at`, and `valid_to` absent or later than `at`.

`GET /api/v1/knowledge/entities/{entity_id}` returns the entity, up to 100 direct relationships, and evidence with the original filename, `project://` URI, quote, heading path, and server-calculated line range. `GET /api/v1/knowledge/relationships/{relationship_id}` returns the relationship and its evidence. Canvas coordinates are not part of the API; layout belongs to the frontend.

Verification on 2026-10-17: 100 backend tests passed; the frontend build and desktop/mobile browser flows passed using isolated SQLite and simulated extraction. Native PostgreSQL 17.10 with pgvector passed migration upgrade/downgrade/re-upgrade, graph/evidence reads, and four concurrent identical confirmations per candidate using independent sessions in a disposable schema. The temporary schema was removed. The application schema was subsequently upgraded to `20261017_0005` to repair missing graph tables; live graph/review/source/search reads returned 200. Real DeepSeek quality, native-database browser acceptance, and Worker/API contention/recovery remain separate checks.

Verification on 2026-10-18: 102 backend tests, the frontend production build, and desktop/mobile real-page walkthrough passed. The application database completed `0005 → 0006 → 0005 → 0006`; pgvector `0.8.7`, the `vector(1024)` column, and cosine operations were confirmed. Tests use simulated embeddings; no embedding provider is configured in the current `.env`, so real semantic-recall quality remains unverified.

Later on 2026-10-18: the full suite reached 104 passing tests after hybrid retrieval was added. A configured real embedding provider and native PostgreSQL/pgvector returned seven indexed hybrid results in the browser, with visible component scores and evidence; that project had no confirmed relationships, so nonzero graph explanations remain covered by automated tests rather than this smoke dataset.

Final verification on 2026-10-18 reached 109 passing backend tests. Focused question tests cover supported answers, citation-boundary rejection, no-evidence refusal without an answer-model call, missing configuration, provider failures, and request validation. The frontend production build and desktop/390 px browser walkthrough passed; the visible answer used a browser-local intercepted response, so real DeepSeek answer quality remains unverified.

## Keyword, semantic-vector, and hybrid graph search

`GET /api/v1/projects/{project_id}/search` supports `mode=keyword`, `mode=vector`, and `mode=hybrid`. Keyword mode retains deterministic name/summary/evidence weighting. Vector mode embeds the query with the configured model and performs exact pgvector cosine-distance ranking over indexed formal entities. Hybrid mode uses fixed `0.3/0.4/0.3` keyword/vector/one-hop graph weights, bounded visible relationships, and returns normalized components plus relationship explanations. All modes support `types`, timezone-aware `valid_at`, and `top_k` and return up to three source evidence records.

Call `POST /api/v1/projects/{project_id}/embeddings/rebuild` before semantic, hybrid, or question requests. It sends formal entity type, name, summary, and evidence to the configured embedding service and writes `knowledge_embeddings`; unchanged model/content hashes are reused. This is separate from confirmation. Vectors are currently fixed at 1024 dimensions and no approximate index is created. See [ADR 0009](../docs/adr/0009-explicit-semantic-index.md) and [ADR 0010](../docs/adr/0010-explainable-hybrid-graph-retrieval.md).

## Evidence-grounded questions

`POST /api/v1/projects/{project_id}/questions` accepts a 1–200 character question and optional timezone-aware `valid_at`. It synchronously runs bounded hybrid retrieval, gives DeepSeek only the selected formal evidence, validates strict JSON and citation membership, and returns only cited evidence with entity and retrieval summaries. With no evidence it returns a deterministic unsupported answer without calling the answer model. Responses are not persisted; history, streaming, and multi-turn orchestration are deferred. See [ADR 0011](../docs/adr/0011-synchronous-evidence-grounded-questions.md).

## Test

```bash
python -m pytest
```

Tests use isolated SQLite databases and cover parsing, API behavior, failure/retry, access isolation, migration upgrade/downgrade with legacy running tasks, offline PostgreSQL SQL compilation, worker recovery/fencing across independent sessions, actual one-shot worker subprocesses, candidate review, formal graph promotion, legacy-confirmation replay, and bounded graph queries. Run `/api/v1/health/ready` against your configured native local services to verify the real PostgreSQL connection. The PostgreSQL dependency must report `up` for acceptance. Offline compilation is not a live database integration test.

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

