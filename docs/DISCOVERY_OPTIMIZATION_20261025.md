# Discovery workflow acceptance — 2026-10-25

[简体中文](DISCOVERY_OPTIMIZATION_20261025.zh-CN.md)

Implemented under [ADR 0047](adr/0047-filtered-discovery-evidence-attribution.md):

- Candidate review combines server-side status, entity/relation kind and literal name/summary filters before pagination. Whole-source review progress stays independent of filtered results. Changing filters discards hidden selections and stale responses.
- Governance filters categories before the result limit and reports counts over the bounded scan. Two-entity findings can open a read-only comparison with separate original evidence, loading/error/retry states and context validation.
- Question evidence shows an identical passage once while retaining all retrieved entity attributions for navigation and model context. Primary entity IDs and canonical citation validation remain unchanged; stored evidence is not merged.

## Verification

The user authorized the agent to execute backend focused/full tests, native PostgreSQL acceptance, frontend tests/build, desktop browser checks and `git diff --check`, without real model calls.

| Check | Actual result |
| --- | --- |
| Focused discovery tests | `tests/test_knowledge_discovery.py`: 4 passed |
| Full backend | `python -m pytest --cov=app --cov-fail-under=90 --cov-report=term --cov-report=xml:../output/backend-coverage.xml --tb=short --show-capture=no`: 632 passed, 5 skipped; 94.48% coverage |
| Native database | `python -m scripts.verify_native`: passed on PostgreSQL 17.10 / pgvector 0.8.7, including discovery regressions; temporary schema removed and application migration marker unchanged |
| Frontend tests | `npm run test:coverage`: 37 tests passed across 7 files |
| Frontend build | `npm run build`: TypeScript checks and production build passed |
| Desktop browser | System Chrome, 1440 × 1100: combined filters, empty results, whole-source progress, side-by-side original evidence, failed read/retry and deduplicated question passage with related entity navigation passed |
| Accessibility | axe checks of review filters, comparison and question regions: 0 violations and 0 incomplete checks; comparison receives focus; no horizontal overflow or browser errors observed |
| Repository checks | `git diff --check` passed; modified Markdown local links resolved; no generated output, dependency directories, `.env` files or detected credential patterns included |

Frontend coverage is scoped by the existing Vitest configuration: statements 55.5%, branches 57.35%; these figures do not describe whole-application coverage. The backend emits an existing Starlette/httpx deprecation warning.

Browser fixtures used a dedicated PostgreSQL schema. Before seeding, ownership checks verified 16 physical private tables; the fixture project was absent from `public`. The named browser session, dedicated API/Vite processes and schema were removed after inspection. Screenshots and temporary scripts remain ignored under `output/discovery-20261025/`.

## Boundaries

Model and embedding outputs were local stubs. This verifies workflow behavior, not real model answer quality, cost or latency. No GitHub synchronization or paid provider calls occurred. Governance category counts cover only its bounded scan; this change adds neither entity merging nor review undo. It requires no database migration or new dependency.
