# Complete local demo and CI

[简体中文](DEMO.zh-CN.md)

Local single-user graduation demo only: authentication is not implemented; do not expose it publicly. Native PostgreSQL/pgvector is the default, Docker optional. Startup makes no paid provider calls.

## Recommended: native Windows

Install Python 3.13, Node 24 and PostgreSQL/pgvector; configure `backend/.env` using [setup](DEVELOPMENT_SETUP.md). First installation:

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,evaluation]"
cd ..\frontend
npm ci
cd ..
.\scripts\start-demo.ps1 -Seed
```

The launcher migrates, optionally creates one new synthetic `[EVAL]` project, then starts hidden API, parsing Worker and frontend processes. Open `http://127.0.0.1:5174`; API docs: `http://127.0.0.1:8001/docs`. Omit `-Seed` to reuse existing projects. Logs are in `output/demo-native/<run>/`. Occupied ports fail without stopping existing services; override with `-ApiPort 8002 -FrontendPort 5175`. Keep the terminal open; Ctrl+C stops only processes held by this launcher, without removing projects or data. Each `-Seed` creates a new project, not a refresh.

## Optional: Docker Compose

```bash
docker compose up -d --build
# Explicit first-time synthetic project initialization:
docker compose --profile demo run --rm demo-init
```

Open `http://localhost:8080`. Services include PostgreSQL/pgvector, API, Worker and nginx frontend with same-origin API proxy and health checks. The database host port defaults to 5433 to avoid native 5432; configure `KA_POSTGRES_PORT`, `KA_API_PORT`, `KA_FRONTEND_PORT` as needed. Ports bind only to loopback. First-time `docker compose --profile demo up -d --build` also starts initialization.

Existing `output/demo/preparation` is refused, preventing duplicate project creation: keep its report and reuse the project. Do not delete business data to retry. `docker compose down` without `-v` preserves the named database volume. Explicit environment variables supply provider keys only to the API, never the frontend image. Parsing, curated graph reads and keyword search need no keys. Semantic indexing, questions and Agent actions require explicit configuration and invocation. Initialization does not build embeddings.

## Demonstration flow

1. Select `[EVAL]` and inspect Markdown/code with exact source lines.
2. Open the formal project graph and navigate evidence back to source chunks.
3. Inspect the historical replacement chain; distinguish curated fixtures from model quality.
4. Select single-step or tool Agent on a code source; invoke only with explicit paid-call approval. Parsing alone is offline.
5. Present the [frozen real experiment report](../evaluation/results/2026-10-24-models/REPORT.md) and figures without more provider calls.
6. State that actual human blind grades are still pending.

## Automated checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term
.\.venv\Scripts\python.exe -m scripts.verify_native
cd ..\frontend
npm run test:coverage
npm run build
cd ..
git diff --check
```

`.github/workflows/ci.yml` defines backend, frontend, disposable pgvector-schema acceptance and container-build jobs on push/PR/manual dispatch. No model keys or provider requests are needed. Coverage is uploaded as CI artifacts and stored locally under `output/`. Component tests cover API errors/cancellation, strategy/retry, running locks, question project changes, search conditions, manual review and inert source text; they are not full-site end-to-end coverage.

Native launcher and PostgreSQL checks were exercised locally. Docker is not installed here, so local image builds remain unverified. A committed workflow is not evidence of a successful hosted GitHub run.

Exact checks and limitations: [delivery acceptance](DELIVERY_ACCEPTANCE.md).
