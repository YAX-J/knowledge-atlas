# Knowledge Atlas Development Setup

M5 offline preparation (2026-10-31): a sealed independent20-task development packet,18-check acceptance matrix, zero-call preflight, reported-run/grade adapter and repeatable local engineering command are implemented. M5 overall remains pending the authorized live executor/fixture replay, real quality, hosted CI, demonstration and release. No real provider calls or business migration; schema stays0023 and historical evaluations/grants/ledgers stay unchanged. See [M5 status and runbook](PROJECT_ASSISTANT_M5.md).

Current M3/M4 schema: `20261031_0023`. Back up and verify recovery before `alembic upgrade head`; API readiness never auto-migrates. Run the existing independent assistant runner for async_v2/v3 queues; no new dependencies/services. [Usage and verification](PROJECT_ASSISTANT_M34.md).

Current source/business head is20261031_0021, upgraded after verified backup/schema recovery and preserved fingerprints. Run `python -m app.assistant_runner` from backend alongside API and the separate source parser. Native start-demo.ps1 and optional Compose include it. Only explicitly submitted async_v2 jobs can invoke the configured model; no historical/failed/expired auto replay. See [M2 usage/verification](PROJECT_ASSISTANT_M2.md); older head notices below describe their original stages.

M1 source head is now `20261031_0020` (additive assistant_tasks), superseding older head announcements below. Read [M1 checks](PROJECT_ASSISTANT_M1.md). The installed database is not automatically upgraded; readiness requires the new head/table. Reuse existing .venv/node_modules; no dependency changes. Back up/rehearse recovery before the normal backend `alembic upgrade head`; disposable verification uses `python -m scripts.verify_native` and preserves the business marker. M1 passed local substitute/native/desktop verification; live quality remains unmeasured.

Offline judging adds EVALUATION_PROVIDER=openrouter with local OPENROUTER_API_KEY, OPENROUTER_MODEL=typesafe/jev-1.14 and OPENROUTER_TIMEOUT_SECONDS=60. See [OpenRouter setup](OPENROUTER_EVALUATION.md). Native CF and direct TypeSafe fields remain supported, without business provider changes. No SDK is added; default evaluation execution remains zero-call preflight. Existing credentials stay local.

Scoped multi-agent workflows now share this application. Update the existing environment with `.\.venv\Scripts\python.exe -m pip install -e ".[dev,evaluation]"` from backend; this installs pinned LangGraph. Back up/rehearse recovery before `alembic upgrade head` to `20261029_0019`. See [roles, API and synchronous human-review boundaries](MULTI_AGENT.md).

[简体中文](DEVELOPMENT_SETUP.zh-CN.md)

Current head: `20261029_0019`. Before upgrading existing data, [back up and verify isolated recovery](BACKUP_RESTORE.md). `/health/ready` checks connection and critical schema without auto-migration. See the [launcher](DEMO.md) and [current acceptance](OPTIMIZATION_20261029.md). Real workbench is the default; provider actions remain explicit.

## Prerequisites

Current requirements:

- Git
- Node.js 22.12 or later (24 LTS recommended)
- npm 10 or later
- Python 3.12 or later
- Natively installed PostgreSQL with pgvector

Local development and real-service acceptance use the user's existing native installations by default. Docker/Compose is an optional alternative. Isolated backend tests use SQLite and do not require database services.

## Optional Neo4j graph snapshots

Start the Neo4j Desktop instance and copy its connection URI. Set these values in the backend's local `.env` file and start or restart the API from `backend/`. Install the updated package with `python -m pip install -e .` in the backend environment if the `neo4j` driver is missing.

```dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=
NEO4J_DATABASE=neo4j
```

Use the actual URI, username, password, and database from your instance. Keep the local `.env` out of Git. Use the existing PostgreSQL connection for `DATABASE_URL`.

1. `GET /api/v1/health/neo4j` should return `{"status":"up"}`.
2. `POST /api/v1/projects/{project_id}/graph/neo4j/sync` should return `node_count`, `edge_count`, and `valid_at` for the written snapshot.
3. `GET /api/v1/projects/{project_id}/graph/neo4j` should return that snapshot's nodes, edges, and effective time. Use `center_id` and `depth` to check traversal.

In the app, open the project's graph and select Neo4j in the data source control. Click **同步到 Neo4j** to sync and show the snapshot time and totals. Choose a center node, set the depth to two hops, and select a relationship to open its source evidence. Repeat the sync after formal knowledge changes. The requests above are also available in FastAPI's `/docs`. See the [API contract](API_CONTRACT.md#neo4j-项目快照) and [ADR 0081](adr/0081-neo4j-project-projection.md).

## Clone and inspect

```bash
git clone https://github.com/YAX-J/knowledge-atlas.git
cd knowledge-atlas
git status
```

Read `README.md`, `AGENTS.md`, and `PLANS.md` before beginning implementation work.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The development server uses `http://localhost:5173` by default.

Available commands:

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start the Vite development server |
| `npm run build` | Run Vue TypeScript checks and build production assets |
| `npm run preview` | Preview the most recent production build |

The demo graph and its node follow-up use local Mock data without credentials. Project/source navigation, candidate review, the project graph and the independent evidence-question workspace use real APIs. Copy `frontend/.env.example` to `frontend/.env` to configure `VITE_API_BASE_URL`; `VITE_DATA_SOURCE=api` opens the source workspace by default. Restart Vite after environment changes. This does not turn the demo graph or its follow-up into real data.

## Backend setup

From the repository root:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment for the current shell, then install the package and development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Create a local environment file from `backend/.env.example`. On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Start your native PostgreSQL service using its existing installation tools. Create a dedicated `knowledge_atlas` database or configure another database name. Set `DATABASE_URL` in `backend/.env` to the actual local values; the example uses localhost port 5432 with placeholder credentials.

PostgreSQL must have pgvector installed. The initial migration executes `CREATE EXTENSION IF NOT EXISTS vector`; the connecting role needs permission, or an administrator must enable the extension in the target database first. From `backend/`, apply migrations and launch the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Useful endpoints:

| Endpoint | Purpose |
| --- | --- |
| `http://localhost:8000/docs` | OpenAPI interface |
| `GET /api/v1/health/live` | Process liveness |
| `GET /api/v1/health/ready` | PostgreSQL dependency health |

To verify ingestion in the OpenAPI interface, create a project, upload UTF-8 Markdown or Java source, call `POST /api/v1/tasks/{task_id}/run`, and query `GET /api/v1/sources/{source_id}/chunks`. Alternatively, run `python -m app.worker` from `backend/` in a second activated terminal to consume uploads automatically. Apply the latest migration first, including execution lease and graph tables. `python -m app.worker --once` handles at most one eligible task and exits. See [backend instructions](../backend/README.md) for configuration, recovery rules, exit codes, and parsing limitations.

Validate the native service setup by running `alembic current` from `backend/` (expected `20261029_0019`) and querying `/api/v1/health/ready`; PostgreSQL must report `up`. Then verify project creation, upload, automatic parsing, duplicate reuse, restart persistence, and worker/API contention against the real local database. SQLite tests do not validate native connectivity, PostgreSQL locking, or pgvector distance operations.

For optional container use, `docker compose up -d --build` from the repository root starts the complete stack. The worker waits for the API to apply migrations and pass its liveness check. Docker is not a prerequisite for acceptance.

## DeepSeek candidate extraction

Apply the latest migration first, including `review_events` and the formal graph tables. Add `DEEPSEEK_API_KEY` to the backend `.env` (never the frontend), retain `DEEPSEEK_BASE_URL=https://api.deepseek.com`, and configure `DEEPSEEK_MODEL` (default `deepseek-flash`). Restart the API, open a parsed source, and choose the candidate-extraction action. It sends that source's chunks to DeepSeek only on explicit request. Review each quote and confirm or reject; a relationship requires both endpoint entities confirmed first. Confirmation writes scoped entities, relationships, and evidence in the same transaction. Worker parsing does not invoke the model. Tests and browser verification use simulated responses; real model acceptance is still required. See [backend instructions](../backend/README.md#deepseek-candidate-extraction-and-review).

## Semantic-vector retrieval

Configure `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, and `EMBEDDING_MODEL` in the backend `.env`; `EMBEDDING_DIMENSIONS` must currently be `1024`. Use “Update semantic index” on the project graph before vector search. Entity text and queries are sent to the configured service; confirmation does not invoke embeddings. Validate the real provider and native pgvector path separately.

## GitHub snapshot import

Optional `GITHUB_IMPORT_MAX_FILES=50` accepts 1–50 files per new scan. Lower budgets reduce anonymous calls and produce explicit incomplete snapshots; a later larger-budget sync reuses saved blobs. Cached complete-snapshot metadata may still exceed a lowered budget without extra blob downloads. Rate limiting can still occur. The opt-in public acceptance uses 30; it does not claim complete-repository coverage.

Public REST repository reads need no credential. For a private repository or Review thread state, set `GITHUB_TOKEN` only in `backend/.env` and grant the minimum read permissions for Contents, Issues, and Pull requests needed by the chosen import. Keep `GITHUB_API_BASE_URL=https://api.github.com`, `GITHUB_GRAPHQL_URL=https://api.github.com/graphql`, `GITHUB_API_VERSION=2026-03-10`, and adjust `GITHUB_TIMEOUT_SECONDS` only when needed. Apply migration `20261022_0014`, register a remote in the source workspace, then explicitly synchronize its default branch/requested ref or import recent Issue/Pull Request versions. A file request imports at most 50 supported files and 20 MiB; a work-item request imports at most 20 items and 20 issue comments per item, plus at most 20 reviews, 20 inline review comments, 20 Review threads, and 20 comment identifiers per thread for each selected PR. Without a token the REST portion still succeeds and reports `review_threads_status=token_required`. Neither path clones, polls, receives webhook event history, invalidates historical evidence, or synchronizes automatically.

## Frontend verification

```bash
cd frontend
npm run build
```

For visible changes, manually verify:

- Search and node selection.
- Evidence expansion and relationship navigation.
- Knowledge-type filtering.
- Timeline playback and detail-panel synchronization.
- Follow-up question states.
- Candidate extraction, review, and legacy-confirmation replay.
- Project graph loading, filtering, one/two-hop neighborhoods, detail evidence, and empty/truncated states.
- Keyword/vector mode switching, index rebuild, unconfigured-provider errors, and index coverage counts.
- Desktop layout (mobile browser acceptance is not required).
- Keyboard focus and panel scrolling.

## Backend verification

Native isolated acceptance: from `backend/`, run `.\.venv\Scripts\python.exe -m scripts.verify_native` (requires pgvector in `public` and `CREATE SCHEMA`). The script qualifies its Alembic version schema and checks that all test tables exist there before tests; it removes only that generated schema. Do not use existing business records as fixtures or assume `search_path=temp,public` alone provides isolation. Add `--github` only after explicitly choosing public GitHub read-only acceptance; no token or model calls are used. The application's actual schema is not upgraded by this test.

```bash
cd backend
python -m pytest
```

The tests override the production database dependency with an isolated SQLite database. They verify the API behavior and model integration, but do not replace a PostgreSQL connectivity check.

## Local services

The backend foundation phase will reserve these defaults:

| Service | Default port | Purpose |
| --- | --- | --- |
| Frontend | `5173` | Vite development server |
| FastAPI | `8000` | REST API (streaming is not implemented) |
| PostgreSQL | `5432` | Business data and pgvector |

These are the defaults for native local services; use your installed database ports when they differ. Run the API, worker, and frontend in separate local terminals. The root `compose.yaml` remains available as an optional container alternative. Backend connection values are overridable through environment variables.

## Environment files

- Commit `.env.example` files containing names and safe development defaults.
- Never commit `.env`, tokens, passwords, private endpoints, or production identifiers.
- Prefix browser-exposed variables with `VITE_` and assume users can read them.
- Keep model-provider keys and GitHub tokens on the backend only.

## Line endings and formatting

- Repository text files use UTF-8 and LF line endings.
- JavaScript, TypeScript, JSON, YAML, CSS, and Markdown use two-space indentation where indentation applies.
- Planned Python code uses four-space indentation.
- Editors should honor the root `.editorconfig` and `.gitattributes` files.

## Troubleshooting

### Dependencies fail to install

Confirm the Node and npm versions, then remove only the local `frontend/node_modules` directory and reinstall. Do not delete unrelated repository files.

### Port 5173 is in use

Run Vite with another port:

```bash
npm run dev -- --port 5174
```

### The page has no real project data

The graph still reads `frontend/src/mock/data.ts`. Open “我的项目” or “资料来源” for real project/source data, start the backend, and confirm `VITE_API_BASE_URL` and the backend `CORS_ORIGINS` match your local addresses. The source workspace reports connection errors and provides retry controls.

### Build output appears in Git status

`frontend/dist`, `node_modules`, Vite caches, and TypeScript build information should be ignored. Check the root `.gitignore` before adding files.

### Readiness returns 503

`/api/v1/health/ready` reports `degraded` while PostgreSQL is unavailable. Check the native service's running state, host/port, database existence, and credentials in `backend/.env`, then apply the latest migration. With optional Docker only, `docker compose ps` can inspect container state.

## CI environment boundaries

The `backend` job installs Python dependencies only. Mocked TypeScript compiler failure tests create a presence-only dependency in a temporary workspace and substitute the process; they must not depend on `frontend/node_modules`. Missing SDK/package tests still check `SEMANTIC_BACKEND_UNAVAILABLE` before any process starts. Real compiler acceptance remains explicit through `KA_NATIVE_COMPILERS=1` and requires the actual SDKs/dependencies.

Provider-free API tests must explicitly inject settings into every route they exercise. The extraction `configured` fixture configures extraction only; question routes need their own injected settings. Never use local `.env` credentials to make tests pass, skip assertions or lower the 90% backend coverage gate to work around CI failures.

In `.github/workflows/ci.yml`, keep the PostgreSQL service option as `--health-cmd "pg_isready -U knowledge_atlas -d knowledge_atlas"`. Actions passes service options to the Docker process; shell-style single quotes can split this command and expose `-U` as a Docker flag. YAML/argument checks are separate from successfully starting a service container. After pushing a fix, confirm both `backend` and `postgres` pass on that new commit before publishing a graduation baseline; rerunning the old commit cannot load the fix.

## Before finishing a task

```bash
git diff --check
git status --short
```

Run the relevant build or tests and report the commands that actually completed.
