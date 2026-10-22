# ADR 0035: Navigate evidence to exact original source chunks

[简体中文](0035-exact-evidence-source-navigation.zh-CN.md)

- Status: Accepted
- Date: 2026-10-22

## Decision

- Add read-only `GET /projects/{project_id}/sources/{source_id}/chunks/{chunk_id}` returning the existing chunk shape, including its zero-based position, exact content, UUID, hash and inclusive lines. Check the non-archived project and joined source/chunk user/project/source scope. Missing/mismatched chunks return 404 `SOURCE_CHUNK_NOT_FOUND`; invalid project access retains its project 404. A surviving parsing task is not required.
- Use source/chunk UUIDs already present in formal graph details, knowledge-search evidence and answer citations. Buttons emit only an `EvidenceLocator` intent; App orchestrates navigation into the source workspace, initial page `floor(position / 20) + 1`, original-chunk focus and existing highlight. Do not guess filenames, parse `project://` strings, search approximate quotes or scan every chunk page.
- Keep dedicated loading/error/retry/cancel state and request fencing. Project/source changes, cancel or leaving the source workspace invalidate pending navigation and detail requests. Do not report success unless the exact chunk is loaded and displayed. Missing/unavailable targets do not fall back to another source or Mock data. A newly started navigation clears old success notices.
- Reuse existing source parsing/review and GitHub links without starting a task/model/provider request. Local chunk navigation changes no evidence text, formal knowledge, temporal semantics or database schema. Current schema head remains `20261022_0014`; Stage 4 remains active.

## Verification

The user previously selected agent execution. Prerequisites: existing backend virtual environment, frontend dependencies and native PostgreSQL/pgvector. Commands:

```powershell
# backend/
.\.venv\Scripts\python.exe -m pytest tests/test_chunk_lookup.py tests/test_parsing.py tests/test_graph.py tests/test_questions.py
.\.venv\Scripts\python.exe -m pytest
# frontend/
npm run build
# repository root
git diff --check
```

Results on 2026-10-22: 32 focused tests and 371 full-backend tests passed, including 13 new chunk-lookup cases. Frontend type checking/build passed. Existing Starlette/httpx deprecation warning remains. Tests cover Markdown/Java exact-byte reads, page-four position without a task, read-only chunk counts, source/chunk/user/project mismatch, archived projects and missing/unparsed chunks.

Native PostgreSQL acceptance uses a task-owned schema and synthetic 65-paragraph source. The exact lookup resolves position 64, line 129; graph and keyword evidence open chunk page 4/4, focus and highlight the original UUID. A transient error is injected only in the temporary harness to verify retry. Browser answer content is explicitly simulated and establishes only citation-navigation behavior, not real model quality.

Desktop checks also passed simulated-answer citation keyboard navigation, cancellation and project-switch stale-response fencing, exact original text and no horizontal overflow. The answer evidence region passed axe-core with zero violations/incomplete checks. Readiness reported PostgreSQL `up`. The task-owned schema/harness were removed and dedicated browser/API/Vite sessions closed after acceptance; existing 8000/5173 services and business data were preserved. Real GitHub/model requests were not made.
