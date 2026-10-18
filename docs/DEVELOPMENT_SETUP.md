# Knowledge Atlas Development Setup

[简体中文](DEVELOPMENT_SETUP.zh-CN.md)

This guide describes the repository setup that exists today and reserves conventions for the planned backend. Commands are written to work from the repository root unless noted otherwise.

## Prerequisites

Current requirements:

- Git
- Node.js 20 or later
- npm 10 or later
- Python 3.12 or later
- Natively installed PostgreSQL with pgvector

Local development and real-service acceptance use the user's existing native installations by default. Docker/Compose is an optional alternative. Isolated backend tests use SQLite and do not require database services. Neo4j has been removed from current requirements; graph storage uses PostgreSQL (see [ADR 0005](adr/0005-postgresql-only-storage.md)). Existing `NEO4J_*` entries can be removed from local environment files; they are ignored by the settings loader.

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

The demo graph and question view use local Mock data and require no database or model credentials. Project/source navigation, candidate review, and the project graph use the real API. Copy `frontend/.env.example` to `frontend/.env` if you need to change `VITE_API_BASE_URL`; set `VITE_DATA_SOURCE=api` to open the source workspace by default. Restart Vite after changing environment values. This does not switch the demo graph or questions to real data.

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

Validate the native service setup by running `alembic current` from `backend/` (expected `20261018_0006`) and querying `/api/v1/health/ready`; PostgreSQL must report `up`. Then verify project creation, upload, automatic parsing, duplicate reuse, restart persistence, and worker/API contention against the real local database. SQLite tests do not validate native connectivity, PostgreSQL locking, or pgvector distance operations.

For optional container use, `docker compose up -d --build` from the repository root starts the complete stack. The worker waits for the API to apply migrations and pass its liveness check. Docker is not a prerequisite for acceptance.

## DeepSeek candidate extraction

Apply the latest migration first, including `review_events` and the formal graph tables. Add `DEEPSEEK_API_KEY` to the backend `.env` (never the frontend), retain `DEEPSEEK_BASE_URL=https://api.deepseek.com`, and configure `DEEPSEEK_MODEL` (default `deepseek-flash`). Restart the API, open a parsed source, and choose the candidate-extraction action. It sends that source's chunks to DeepSeek only on explicit request. Review each quote and confirm or reject; a relationship requires both endpoint entities confirmed first. Confirmation writes scoped entities, relationships, and evidence in the same transaction. Worker parsing does not invoke the model. Tests and browser verification use simulated responses; real model acceptance is still required. See [backend instructions](../backend/README.md#deepseek-candidate-extraction-and-review).

## Semantic-vector retrieval

Configure `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, and `EMBEDDING_MODEL` in the backend `.env`; `EMBEDDING_DIMENSIONS` must currently be `1024`. Use “Update semantic index” on the project graph before vector search. Entity text and queries are sent to the configured service; confirmation does not invoke embeddings. Validate the real provider and native pgvector path separately.

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
- Desktop and mobile layouts.
- Keyboard focus and panel scrolling.

## Backend verification

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
| FastAPI | `8000` | REST and streaming API |
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

## Before finishing a task

```bash
git diff --check
git status --short
```

Run the relevant build or tests and report the commands that actually completed.
