# ADR 0003 Persist Markdown chunks and run parsing explicitly

- Status: Accepted
- Date: 2026-10-17

The persistence and parsing decisions remain accepted. The explicit-only execution scope and missing recovery described at adoption are extended by [ADR 0004](0004-database-backed-parsing-worker.md), which adds an optional database-backed worker and leases while retaining the manual endpoint.

## Context

Uploads already persist original Markdown and a queued task. The current slice needs reproducible evidence locations without a model service or a deployed queue.

## Decision

- Persist source chunks in PostgreSQL with user/project/source UUIDs, original text, one-based inclusive line ranges, heading paths, and SHA-256 hashes. Chunk UUIDs are deterministic within an immutable source.
- Support top-level ATX/Setext headings, paragraphs, lists, and fenced code. Preserve other Markdown as text; this is a structural subset rather than a complete CommonMark renderer.
- Expose a synchronous `POST /tasks/{task_id}/run` development endpoint. Claim queued or failed tasks with an atomic conditional update, commit the claim, and write all chunks plus final status in one transaction. Re-running a succeeded task returns its existing result; running tasks return a conflict.
- Reuse the existing source and task for identical bytes within one user's project, independent of filename. Serialize upload creation using the project row lock on PostgreSQL. Different bytes create a new immutable source; cross-project uploads remain separate.
- Keep parsing separate from knowledge extraction. A ready source means parsing completed, not that knowledge was extracted or confirmed.

## Consequences

Parsing is observable and testable with the current service. Uploads remain queued until explicitly executed. There is no automatic queue consumer, timeout recovery for interrupted running tasks, full Markdown syntax tree, or incremental source revision model yet. SQLite tests verify behavior but do not establish PostgreSQL locking guarantees.

## Alternatives considered

In-process background tasks obscure failures and do not survive restarts. A separate queue/worker adds deployment scope before parsing is stable. Both can later call the same parsing service. Enforcing a new source-hash uniqueness constraint now could reject migrations on databases containing earlier duplicate uploads.
