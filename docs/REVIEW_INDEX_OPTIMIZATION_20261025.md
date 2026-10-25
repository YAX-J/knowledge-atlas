# Batch review and index status acceptance (2026-10-25)

[简体中文](REVIEW_INDEX_OPTIMIZATION_20261025.zh-CN.md)

The user requested further project optimization; their explicit choice of Agent-run verification carries forward. Repository review/frontend/docs/verification skills were used. No real provider calls or GitHub synchronization occurred.

## Implemented

- Explicit same-source confirmation/rejection of 1–100 unique candidates. Validate all IDs, hold the project lock, order entities before relationships, reuse review/audit/promotion services and commit once. Any failure rolls back the batch; same-action retries are idempotent.
- Visible pending-item selection, named preview and final confirmation. Page changes discard hidden selections; unsaved edits block bulk actions. Fixed missing project/source/navigation locks during review requests.
- Provider-free project/time-scoped index status reports missing rows, matching index counts and stale content hashes. Inspect at most 1000 entities with explicit truncation. Refresh after explicit rebuild and discard late responses from prior projects/times.

See [ADR 0046](adr/0046-atomic-batch-review-index-status.md). No migration, undo, entity merge or automatic indexing is introduced.

## Actual verification

- Backend focus: 48 passed, followed by an additional invalid-relation-evidence regression proving promoted entities and audit events roll back together.
- Final full backend: `python -m pytest --cov=app --cov-fail-under=90 --cov-report=term --cov-report=xml:../output/backend-coverage.xml --tb=short --show-capture=no`: 628 passed, 5 conditional skips, 94.45% application statement coverage. Existing Starlette/httpx deprecation warning remains.
- `python -m scripts.verify_native`: PostgreSQL 17.10 / pgvector 0.8.7 migrations, concurrency/lease checks and new review/status tests passed. Disposable schema removed; application migration marker unchanged.
- Frontend `npm run test:coverage`: 30 passed; existing limited coverage scope: 52.45% statements, 53.58% branches. Final `npm run build` passed.
- System Chrome 1440×1100 with native PostgreSQL synthetic fixtures: relation-only rejection, selected entities/relationship preview and atomic success, updated source totals, and navigation protection during persistence. A 1.8-second delayed local response kept checkboxes disabled and navigation on the source page.
- Free status refresh retained 0/2 indexed and two missing. Explicit rebuilding with local simulated vectors changed status to 2/2, zero missing/stale. This is not model-quality acceptance. Search-region axe-core 4.12.1: zero violations/incomplete checks; visible 2px keyboard focus, no horizontal page overflow or browser exceptions.
- `git diff --check` and 356 documentation links in changed files passed. No secrets, dependencies, build output or temporary QA scripts are tracked.

## QA fixture isolation correction

The first browser fixture initializer used `Base.metadata.create_all`; PostgreSQL existence checks fell back through search_path to public, placing the generated test project in the application data area. Stopped the QA API and verified the exact project/source UUIDs, fixed synthetic content hash, three pending candidates and absence of formal knowledge/audits. Backed up then transactionally removed only this fixture: one project/source, two tasks, three candidates and chunks. Existing user projects were not included in cleanup.

Recreated QA with forced table creation and table-ownership assertions before any fixture writes; confirmed 16 private-schema tables and no fixture project in public. Completed browser acceptance in the corrected environment. Closed the named browser and dedicated services, released ports 8001/5174, removed the QA schema and confirmed both generated fixture UUIDs are absent from public.

Production code was unaffected by this correction. Future native QA must verify actual table ownership before fixture writes; current_schema or create_all alone is insufficient.
