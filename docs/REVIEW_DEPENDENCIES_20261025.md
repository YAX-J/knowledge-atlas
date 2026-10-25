# Relation review dependencies — 2026-10-25

[简体中文](REVIEW_DEPENDENCIES_20261025.zh-CN.md)

Under [ADR 0048](adr/0048-review-endpoint-visibility.md), relation review cards now show both entity names and statuses even when those entities are filtered out or on other pages. Single confirmation requires confirmed endpoints. Batch confirmation also accepts current-page pending entities explicitly selected by the user; unmet dependencies appear by name before final submission. Rejection remains available. The entity-list action resets filters and hidden selections, then focuses the review heading.

The backend enriches a listing with one bounded lookup of at most two endpoint IDs per relation, checking exact user/project/source/successful-task/entity-kind scope. Metadata is a read-time snapshot; authoritative review locks, dependency/evidence validation, atomic rollback and promotion are unchanged. This requires no migration, dependency or model call.

## Verification

The user previously selected agent execution; the agent ran:

| Check | Result |
| --- | --- |
| Focused backend | `python -m pytest tests/test_knowledge_discovery.py tests/test_batch_reviews.py tests/test_knowledge.py --tb=short --show-capture=no`: 36 passed |
| Full backend | `python -m pytest --cov=app --cov-fail-under=90 --cov-report=term --cov-report=xml:../output/backend-coverage.xml --tb=short --show-capture=no`: 638 passed, 5 skipped; coverage 94.49% |
| Native PostgreSQL | `python -m scripts.verify_native`: passed on PostgreSQL 17.10 / pgvector 0.8.7, including source/task/kind boundary tests; schema removed, application migration marker unchanged |
| Focused frontend | `npm test -- tests/review.test.ts tests/appRequests.test.ts`: 19 passed |
| Full frontend | `npm run test:coverage`: 57 tests passed across 8 files; scoped statements 63.56%, branches 60.54% |
| Production build | `npm run build`: passed |
| Desktop browser | Chrome 1440 × 1100: relation-only filtering shows two pending endpoints and disables single/final batch confirmation; entity navigation clears selection/preview and focuses the review heading; explicitly confirming both entities enables the relation, which then confirms successfully; whole-source progress ends at 0 pending / 3 confirmed |
| Accessibility | Review-region axe: 0 violations, 0 incomplete checks; no horizontal overflow or browser errors; confirmed relation heading receives focus |

Backend tests retain one existing Starlette/httpx deprecation warning. Frontend coverage describes the configured subset, not the entire site. Before commit, `git diff --check`, changed Markdown links and tracked-file hygiene were checked.

Browser fixtures used a dedicated native PostgreSQL schema whose physical table ownership was verified before any fixture write; the fixture project was absent from `public`. The named browser, recorded API/Vite processes and schema were removed afterward. Screenshots/scripts/logs remain ignored under `output/review-dependencies-20261025/`.

All provider outputs were local stubs; no real model/embedding or GitHub request was made. This validates dependency handling, not extraction quality. Status can change after listing, so backend conflict responses still require refreshing the review list. No automatic selection, entity merge or review undo was introduced.
