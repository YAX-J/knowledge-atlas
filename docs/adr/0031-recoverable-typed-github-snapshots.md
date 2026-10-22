# ADR 0031: Recover incomplete GitHub snapshots with typed source reuse

[简体中文](0031-recoverable-typed-github-snapshots.zh-CN.md)

- Status: Accepted
- Date: 2026-10-22
- Supplements: ADR 0019 for cache eligibility and reuse identity.

## Context

An unconditional same-commit shortcut makes a truncated or size-limited snapshot impossible to complete through the existing Sync action. Blob-only reuse also lets Markdown/Java extension changes inherit the wrong source and parser task. A truncated file selection does not establish that an old path disappeared.

## Decision

- Short-circuit a repeated ref/commit only when the latest snapshot is not truncated, deletion detection is complete, and all successful file references remain compatible. Deterministic empty/encoding/path skips may be cached; size-limit skips remain retryable.
- Otherwise the next explicit Sync action re-reads the bounded tree, reuses successful files and retries missing/skipped work, saving a new immutable snapshot even for the same commit. Existing limits remain 50 selected files and 20 MiB of downloads per attempt. No automatic retry or pagination is added; the fixed selection limit can still prevent complete import.
- Match reusable provenance by blob SHA and source type. Join snapshot/source/task records and validate user/project/repository ownership, task-to-source membership, and parser type. Preserve compatible legacy Markdown parsing tasks. Do not rerun ordinary failed parsing tasks automatically.
- Markdown/Java extension changes create or reuse correctly typed sources/tasks rather than rename incompatible sources. Same-type `.md`/`.markdown` moves may still reuse. Missing or incompatible cached links trigger recovery without rewriting historical snapshot records.
- Only a complete tree/file selection can establish a rename; incomplete selections may reuse content but cannot change the source display path as a guessed rename. Existing conservative deletion rules and non-destructive evidence history remain.
- Retain API shapes, frontend actions, database schema, and the reviewed-knowledge boundary. No real-provider calls, polling/webhooks, destructive repair, or compiler integration is required for this change.

## Consequences

Users can recover byte-limited imports or retry after changing limits through the existing Sync action, while complete snapshots keep the cheap shortcut. Recovery avoids duplicate same-type sources and parser mismatches. Old snapshots and evidence remain available; this does not repair historical parsed content or certify real GitHub/PostgreSQL behavior.

## Verification

Continue with the user's selected agent executor. Existing backend virtual environment, isolated SQLite, and HTTP fixtures are sufficient; no GitHub/LLM token or migration is required.

```powershell
# backend/
.\.venv\Scripts\python.exe -m pytest tests/test_github_sync_recovery.py tests/test_github_import.py tests/test_sources.py tests/test_parsing.py tests/test_source_list.py
.\.venv\Scripts\python.exe -m pytest
# repository root
git diff --check
```

Expected: recovery preserves successful IDs/history, complete snapshots avoid tree/blob requests, cross-type changes use the correct parser, foreign/broken references are rejected, and incomplete selections do not imply renames/deletions. Native PostgreSQL, real GitHub, and browser acceptance remain separate.

Agent-executed results on 2026-10-22: 51 focused tests (including 19 recovery cases) and 294 full-backend tests passed. One existing Starlette deprecation warning remains. Tests used isolated SQLite and simulated HTTP responses outside the Windows sandbox, continuing the user's selected executor. No real GitHub/LLM, native PostgreSQL, or browser acceptance was performed.
