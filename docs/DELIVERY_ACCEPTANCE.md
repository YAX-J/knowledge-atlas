# Delivery acceptance: graduation items 3–8

[简体中文](DELIVERY_ACCEPTANCE.zh-CN.md)

Date: 2026-10-24. Executor: Agent, following the user's existing selection. Commands use the project virtual environment; no provider calls were made by ordinary tests.

| Check | Actual result |
| --- | --- |
| Full backend `python -m pytest --cov=app --cov-report=term --cov-report=xml:../output/backend-coverage.xml` | 592 passed, 5 opt-in checks skipped, 94% application statement coverage; one existing Starlette/httpx deprecation warning |
| Focused call tools / dataset / acceptance / charts | Passed; invalid tools, scope, arguments, forged targets and loop budgets covered |
| Frontend `npm run test:coverage` | Strict source/test type check and 15 tests passed; limited client/four-component coverage: statements 50%, lines 49.82%, branches 47.31%, functions 30% |
| Frontend `npm run build` | Vue type check and production build passed |
| `python -m scripts.verify_native` | Native PostgreSQL 17.10 / pgvector 0.8.7 disposable-schema migration upgrade/downgrade/re-upgrade, integration, contention/lease and initialization passed; schema removed, application marker unchanged |
| `scripts/start-demo.ps1` without `-Seed` | API 8001 / Worker / Vite 5174 started and readiness passed; Ctrl+C cleaned the owned processes and released both ports |
| Desktop system Chrome, 1440×1100 | Selected tools mode, keyboard Enter, real no-candidate response without provider calls; simulated browser-only loading/error and real empty-result retry; no page errors or horizontal overflow; source region axe audit: 0 violations |
| Five scientific charts | Generated offline from frozen results, visually inspected, PNG/SVG plus numerical values and input SHA-256 retained |
| `git diff --check` | Passed |

Backend tests require unsandboxed execution on this Windows host because sandboxed TestClient/socket behavior can hang; no business-code workaround was introduced. UI failure simulation is not provider-quality evidence. Real model acceptance is separately documented in the [experiment report](../evaluation/results/2026-10-24-models/REPORT.md): 112 requests within the authorized 172, public synthetic inputs only, no new embeddings. No further model calls were made during the desktop walkthrough.

Coverage gates: backend 90% application statements; frontend scoped minimums statements/lines 45%, branches 40%, functions 25%. These are initial regression floors, not claims of complete UI coverage.

Not verified here: Docker image builds (Docker unavailable), hosted GitHub CI (workflow added but not dispatched), independent human blind grades, extraction semantic quality and representative/private repository model quality. No new authentication or public deployment is supplied. Human scores remain null/blank, not inferred from automatic checks. This delivery completes implementation and recorded automatic acceptance, not the remaining human experiment.
