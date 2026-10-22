# ADR 0033: Import saved commit messages as evidence sources

[简体中文](0033-saved-commit-evidence-sources.zh-CN.md)

- Status: Accepted
- Date: 2026-10-22

## Decision

- Add explicit `POST /projects/{project_id}/repositories/{repository_id}/snapshots/{snapshot_id}/commit-source`, with no request body, to render locally saved GitHub SHA, UTC commit time, and commit message into ordinary Markdown. No provider/model call or automatic parsing/extraction/review is performed by this endpoint. Existing workers may consume its queued parsing task.
- Keep user, non-archived project, repository and snapshot boundaries. Validate the commit SHA before using it in a filename. Reuse existing UTF-8/size checks, SHA-256 repository/type-scoped deduplication and project-row locking. Preserve current task status on reuse, and repair missing/incompatible snapshot mappings through ordinary ingestion rather than trusting foreign references.
- Exclude ref, sync counts and mutable repository coordinates from the rendered bytes. Repeated identical saved metadata across refs/renames reuses a source; different commits/repositories remain separate. Empty messages produce explicit empty-message text and the same source-boundary warning.
- Add only nullable `commit_source_id` / `commit_task_id` foreign keys (`SET NULL`) and a source index to snapshots in reversible migration `20261022_0014`. Original commit/file synchronization facts stay unchanged; only the import mapping is enriched. Downgrading removes mappings, not sources/tasks/chunks; reimport can deduplicate them after re-upgrade.
- Derive canonical current-remote `/commit/{sha}` links for source and formal graph/search/question evidence. Local Markdown line numbers are not patch locators and must not become fabricated GitHub `#L` fragments. Preserve application `project://` provenance and ordinary evidence validation.
- Add a desktop saved-history panel with ten-item pagination, loading/empty/error/retry, bounded scrolling, canonical links and explicit import/open. App-level counters fence history responses; commit imports use the existing context lock and open/focus the original source/task after refreshing lists.

## Consequences

Commit messages can participate in the existing parse → explicit model candidates → human review → formal knowledge workflow. They are statements by commit authors, not proof of implementation correctness. No formal Commit entity, automatic relationship, patch/parent-history import, polling, webhook or full Git history is introduced. Stage 4 remains active. Migration must be applied before running the updated application; no business-schema upgrade is performed by the temporary acceptance harness.

## Verification

The user selected agent execution. With the existing backend virtual environment and frontend dependencies:

```powershell
# backend/
.\.venv\Scripts\python.exe -m pytest tests/test_commit_sources.py tests/test_migrations.py
.\.venv\Scripts\python.exe -m pytest
# frontend/
npm run build
# repository root
git diff --check
```

Results on 2026-10-22: 28 focused tests and 333 full-backend tests passed (17 new cases); frontend type checking/build passed. Existing Starlette/httpx deprecation warning remains. Tests cover scope/archive boundaries, deterministic content, reuse/current status, missing/foreign mapping recovery, limits, untrusted messages, SQLite migration preservation/roundtrip, PostgreSQL offline SQL, and a simulated-model extraction → review → commit evidence path. Simulated responses do not establish real model quality.

Native PostgreSQL acceptance in a task-owned temporary schema passed migration upgrade → downgrade → re-upgrade and concurrent imports of the same commit from two refs with one source/task. Desktop acceptance uses isolated API/Vite ports 8001/5174 and public synthetic fixtures; it does not read GitHub, invoke a real model, or stop existing 8000/5173 services.

Desktop walkthrough passed loading, injected transient error/retry, ten-item pagination, empty history, long-message keyboard scrolling/visible focus, import/open reuse, manual parsing into six original chunks, canonical commit URLs, and project-switch stale-response cleanup. The complete new panel had zero axe-core violations; one color-contrast incomplete check caused by scroll clipping passed after scrolling that row into view. Computed muted/body contrast against the panel is 5.34:1 / 14.28:1. Readiness reported PostgreSQL `up`. Task-owned schema, harness and browser/API/Vite sessions were removed/closed after acceptance; existing business data was not migrated or deleted.
