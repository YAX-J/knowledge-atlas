# ADR 0032: Search bounded Java source symbols and open original chunks

[简体中文](0032-bounded-code-symbol-search.zh-CN.md)

- Status: Accepted
- Date: 2026-10-22

## Decision

- Add read-only `GET /projects/{project_id}/code-symbols` for ready Java sources, with required literal case-insensitive name/path query, optional repository and kind, and 1–100 returned hits (default 50). Preserve user/project/repository access checks and distinct immutable source versions.
- Share the exact declaration/symbol generator with the single-file outline, avoiding repeated call analysis or a second persistent index. Scan oldest-first up to 100 sources and 20 MiB of text, at most 200 symbols each. Exact names rank before qualified-name and path-only matches; stable path/line/kind/UUID ordering breaks ties.
- Return original symbol/source/repository/task identities, lines, nullable chunk ID/zero-based position, and existing commit/line-pinned GitHub URLs. `scanned_source_count` and `matched_count` describe only the bounded scan; `truncated` covers every scan/output omission. This is not a compiler-wide index or reviewed code knowledge.
- Add a source-workspace form and scrollable result list. App-level request counters invalidate edited/cleared/project-changed/navigation-changed requests. Opening a hit loads its source and the correct chunk page (existing default 20), then focuses/highlights the original chunk; ready legacy sources remain readable without a task mapping.
- Retain existing frontend conventions, database schema, knowledge-review boundary and no-model behavior. Do not add a compiler, database migration, router/store, global semantic index, source mutation, or new formal entity type.

## Verification

Continue with the user's selected agent executor. Use the existing backend virtual environment and frontend dependencies:

```powershell
# backend/
.\.venv\Scripts\python.exe -m pytest tests/test_code_search.py tests/test_java_v1.py tests/test_java_structure.py tests/test_java_static_imports.py tests/test_parsing.py
.\.venv\Scripts\python.exe -m pytest
# frontend/
npm run build
# repository root
git diff --check
```

Desktop browser acceptance uses the real API and native PostgreSQL in a task-owned temporary schema, ports 8001/5174, and public fixtures. Cover filters, original source/page/focus, long paths, scrolling, empty/retry/clear states, and stale responses on project switch. Fault/delay states may be injected only in the temporary harness. No GitHub/LLM acceptance is implied.

Agent results on 2026-10-22: 149 focused and 316 full-backend tests passed, including 22 new search cases; the existing Starlette deprecation warning remains. Frontend build passed. Native PostgreSQL desktop checks passed, including a jump to method64 at line 66 on chunk page 4/4, long paths, the 50-hit limit, filters, empty results, retry, clear/focus and project-switch response fencing. The new search region passed axe-core with zero violations and zero incomplete checks. No migration, real GitHub or model call was used.

Final desktop recheck also confirmed that leaving for evidence questions and returning to sources clears the form/results. Both task-owned PostgreSQL schemas were removed and the dedicated browser/API/frontend sessions were closed; existing ports 8000/5173 were preserved.

## Limits

Only the currently supported Java declarations can match. Results from earlier immutable versions remain separate. The first 100 eligible sources are not complete repository coverage; narrowing the repository/query does not guarantee finding later omitted files. UI repository options reflect the loaded repository-list page. Stage 4 remains active.
