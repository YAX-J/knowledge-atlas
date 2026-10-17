# Knowledge Atlas Development Setup

This guide describes the repository setup that exists today and reserves conventions for the planned backend. Commands are written to work from the repository root unless noted otherwise.

## Prerequisites

Current requirements:

- Git
- Node.js 20 or later
- npm 10 or later
- Python 3.12 or later
- Docker Desktop or a compatible Docker Engine
- Docker Compose v2

Docker is required for PostgreSQL/pgvector and Neo4j, but the isolated backend tests run against SQLite without Docker.

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

The current application uses local Mock data and requires no database or model credentials.

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

Start the databases from the repository root, apply migrations, and launch the API:

```bash
docker compose up -d postgres neo4j
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

Useful endpoints:

| Endpoint | Purpose |
| --- | --- |
| `http://localhost:8000/docs` | OpenAPI interface |
| `GET /api/v1/health/live` | Process liveness |
| `GET /api/v1/health/ready` | PostgreSQL and Neo4j dependency health |

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
- Desktop and mobile layouts.
- Keyboard focus and panel scrolling.

## Backend verification

```bash
cd backend
python -m pytest
```

The tests override the production database dependency with an isolated SQLite database. They verify the API behavior and model integration, but do not replace a PostgreSQL/Neo4j connectivity check.

## Local services

The backend foundation phase will reserve these defaults:

| Service | Default port | Purpose |
| --- | --- | --- |
| Frontend | `5173` | Vite development server |
| FastAPI | `8000` | REST and streaming API |
| PostgreSQL | `5432` | Business data and pgvector |
| Neo4j HTTP | `7474` | Neo4j browser and HTTP |
| Neo4j Bolt | `7687` | Application graph connection |

The root `compose.yaml` provides these services. Backend connection values remain overridable through environment variables.

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

This is expected in the current phase. The application reads `frontend/src/mock/data.ts`. Real API integration is planned after the backend foundation is complete.

### Build output appears in Git status

`frontend/dist`, `node_modules`, Vite caches, and TypeScript build information should be ignored. Check the root `.gitignore` before adding files.

### Readiness returns 503

`/api/v1/health/ready` reports `degraded` while PostgreSQL or Neo4j is unavailable. Check `docker compose ps`, confirm the values in `backend/.env`, and apply the latest migration.

## Before finishing a task

```bash
git diff --check
git status --short
```

Run the relevant build or tests and report the commands that actually completed.
