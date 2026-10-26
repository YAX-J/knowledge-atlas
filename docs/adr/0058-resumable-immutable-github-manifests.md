# ADR 0058 Resumable immutable GitHub manifests

[简体中文](0058-resumable-immutable-github-manifests.zh-CN.md)

- Status: Accepted
- Date: 2026-10-26

## Decision

Extend snapshot import (ADR 0018/0019) with cached scan_state and explicit continue_from_snapshot. Pin commit/tree/ref and validate tenant/project/repository. Recursive truncation falls back to bounded directory BFS, persisting frontier without mutating earlier snapshots. Limit each step to 10 directory reads and 50 file downloads / 20 MiB, manifests to 250,000 entries/depth 64. Complete sequences reconcile deletions against the previous different commit; incomplete snapshots never assert full deletion detection.

## Consequences and alternatives

Unbounded synchronous scans were rejected. A truncated individual directory remains explicitly blocked, with local folder import as fallback. Private acceptance needs actual authorization; simulated scope tests do not prove private connectivity.
