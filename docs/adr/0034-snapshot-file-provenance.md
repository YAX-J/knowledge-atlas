# ADR 0034: Read saved snapshot file provenance

[简体中文](0034-snapshot-file-provenance.zh-CN.md)

- Status: Accepted
- Date: 2026-10-22

## Decision

- Expose read-only `GET /projects/{project_id}/repositories/{repository_id}/snapshots/{snapshot_id}/files`, with stable path/UUID pagination (default 20, maximum 100). Scope the non-archived project, repository and snapshot before counting or reading files. Reuse existing tables and schema head `20261022_0014`; no migration/provider/model call is introduced.
- Preserve stored import/reuse/unchanged/rename/delete/skip facts, original paths, blob IDs, sizes and skip reasons. Return snapshot completeness flags and saved-record total, not complete repository coverage. Pagination cannot recover files omitted by the original synchronization bounds. This is not a patch or Git diff.
- Outer-join only source/task link metadata, without loading source bodies or task results. Expose nullable source IDs only when user/project/repository/source type match; task IDs additionally require correct source association and parser type, including legacy Markdown parsing. Missing/incompatible links are unavailable, not repaired by this read. Skipped records do not provide source navigation. Ready sources remain readable without a task.
- File URLs use the selected snapshot's commit/path and current canonical remote, independently of the source's most recent occurrence. Validate paths/SHA before generating links. Deleted paths have no file link into the deletion commit, but can still open retained local sources. Source detail/evidence views retain their existing source-level provenance rules; shared sources may have a different display path.
- Add a separate props/events-only `SnapshotFiles.vue`. App-level request counters discard stale file pages after repository/history-page/snapshot/project changes or close. Preserve requested page on retry; support bounded scrolling, long paths, loading/empty/error/retry, keyboard panel/source focus and close-to-opener focus return. Original-source navigation reuses parsing/review; it does not download or extract automatically.

## Consequences

Users can inspect which saved files contributed to a synchronization snapshot and read retained originals after rename/deletion. This does not create authoritative code entities, temporal replacements, Git history/diffs, or destructive deletion propagation. Stage 4 remains active. Existing installations still need schema head `20261022_0014`, but this feature adds no migration and acceptance does not modify business data.

## Verification

Continue with the user's selected agent executor using the existing virtual environment and frontend dependencies:

```powershell
# backend/
.\.venv\Scripts\python.exe -m pytest tests/test_snapshot_files.py tests/test_commit_sources.py tests/test_github_import.py tests/test_github_sync_recovery.py
.\.venv\Scripts\python.exe -m pytest
# frontend/
npm run build
# repository root
git diff --check
```

2026-10-22 results: 69 focused tests and 358 full-backend tests passed, including 25 new file-history cases. Frontend type checking/build passed. Existing Starlette/httpx deprecation warning remains. Coverage includes six saved states, scope/archive isolation, missing/foreign/type-incompatible links, exact encoded commit URLs, rename coordinates, empty/out-of-range pages, bounds, read-only counts and invalid paths.

Native PostgreSQL acceptance uses a disposable task schema with synthetic Markdown/Java sources, renamed/deleted/skipped records and 24 saved files. It checks native query behavior and actual API/Vue navigation on isolated ports 8001/5174; no real GitHub/model acceptance is implied.

Desktop checks passed loading, injected error/retry, 20/4-row pagination, empty snapshots, long-path wrapping, bounded keyboard scrolling and visible focus, retained deleted-source Markdown chunks, Java source/structure navigation, close-to-opener focus, and stale-response fencing on snapshot/project changes. The new panel had zero axe-core violations; a contrast incomplete check caused by scroll clipping was rechecked on individual visible rows with zero violations/incomplete checks. API readiness reported PostgreSQL `up`. The task-owned schema and temporary harness were removed and browser/API/Vite sessions closed; existing 8000/5173 services and business data were preserved.
