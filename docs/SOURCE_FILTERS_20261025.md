# Source discovery acceptance — 2026-10-25

[简体中文](SOURCE_FILTERS_20261025.zh-CN.md)

[ADR 0049](adr/0049-source-discovery-filters.md) adds combined filename/relative-path, language and source parsing-state filters before pagination. The original default, user/project/archive boundaries, task links and provenance remain intact. The UI preserves the opened original across filtering, distinguishes no matches from an empty project, focuses the list heading after applying filters and resets conditions when changing projects. Failed pagination retries the requested page; a disappeared page recovers to the last valid page. No migration or dependency was added.

## Verification

The agent executed these checks under the user's standing authorization:

| Check | Result |
| --- | --- |
| Focused backend | `python -m pytest tests/test_source_filters.py tests/test_sources.py --tb=short --show-capture=no`: 17 passed |
| Full backend | `python -m pytest --cov=app --cov-fail-under=90 --cov-report=term --cov-report=xml:../output/backend-coverage.xml --tb=short --show-capture=no`: 643 passed, 5 skipped; coverage 94.50% |
| Native database | `python -m scripts.verify_native`: passed on PostgreSQL 17.10 / pgvector 0.8.7, including the source filter suite; temporary schema removed, application migration marker unchanged |
| Focused frontend | `npm test -- tests/workspaces.test.ts tests/appRequests.test.ts tests/client.test.ts`: 32 passed |
| Full frontend | `npm run test:coverage`: 65 tests passed across 8 files; configured statements 64.43%, branches 63.73% |
| Build | `npm run build`: strict TypeScript and production build passed |
| Desktop browser | System Chrome 1440 × 1100, real local API and 26-source native PostgreSQL fixture: combined `src/storage_100%` + Python + uploaded matched one file; ready produced zero results while preserving the opened Python source; reset restored two pages; one browser-local second-page failure retried to page 2 with 6 records and the same selected source |
| Accessibility | Source-filter axe: 0 violations, 0 incomplete checks; correct heading focus, no horizontal overflow or browser errors |

Before commit, `git diff --check`, changed Markdown links and tracked-file hygiene were checked. Frontend coverage describes configured files, not the whole application. Backend retains the existing Starlette/httpx deprecation warning.

The browser schema physically owned all business tables before fixture writes; the generated project was absent from `public`. The named browser, recorded API/Vite processes and validated schema were cleaned up. Temporary screenshots, scripts and logs remain ignored under `output/source-filters-20261025/`.

No real model/embedding or GitHub request was made. Filters inspect filenames/paths and source-record states, not full content or task-state history. Filtering performs no automatic parse, extraction or review, and does not change formal knowledge.
