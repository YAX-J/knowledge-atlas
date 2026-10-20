# ADR 0019: Persist incremental GitHub commit snapshots

[简体中文](0019-incremental-github-commit-snapshots.zh-CN.md)

- Status: Accepted
- Date: 2026-10-20

## Decision

Each successful explicit GitHub synchronization persists an immutable repository snapshot containing the resolved ref, commit/tree SHA, commit URL/message/time, bounded-result flags, change counts, and one file record per selected supported blob. The repository also stores GitHub's stable provider repository ID and adopts the canonical owner/name returned by GitHub, so an upstream repository rename does not silently replace its identity.

For the same ref, the immediately preceding snapshot is the incremental baseline. An unchanged path/blob reuses its prior source without downloading the blob. A blob already present at another path also reuses its source; a single prior path that disappeared is reported as a rename. Paths missing from a complete new tree are recorded as deleted. A repeated request for the same consecutive commit reuses the persisted snapshot without reading its tree or blobs.

Deletion reconciliation is authoritative only when the recursive tree and the 50-file/20-MiB budgets are not truncated. Remote deletion does not physically delete immutable sources, parsed chunks, reviewed knowledge, or evidence. It is preserved as snapshot history for later temporal-governance decisions.

## Consequences

- Branch advances download only new or changed blobs while preserving the existing validation, deduplication, task, and evidence pipeline.
- Snapshot history is queryable through a project/repository-scoped read endpoint and remains isolated by user and project.
- Unambiguous file renames update the source's current display path while the old path remains in the prior snapshot.
- Copies and ambiguous same-blob moves reuse content but are not guessed as renames.
- This slice does not add webhooks, polling, force-push ancestry analysis, source/knowledge invalidation, immutable line URLs, full commit-diff import, Issues, or Pull Requests.
