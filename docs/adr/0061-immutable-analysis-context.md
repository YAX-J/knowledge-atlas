# ADR 0061 Immutable analysis context

[简体中文](0061-immutable-analysis-context.zh-CN.md)

- Status: Accepted
- Date: 2026-10-29

## Decision

Extend ADR 0059 with provider-free `GET /sources/{id}/analysis-contexts` and optional `snapshot_id` / repeated `version_ids` on explicit call analysis. Every strategy selects context before helpers/providers. A snapshot uses its immutable paths and source membership; subsequent source renames cannot change those views. Default to the most recent complete eligible snapshot, otherwise the most recent partial snapshot. Local mode picks the newest ready version per path, with explicit one-version overrides; the current file stays fixed.

Scope all choices by user/project/repository and compatible language. Reject mixed contexts, foreign IDs, missing current-source membership, or one source mapped to multiple paths. Inspect metadata before loading bounded bodies: at most 2000 metadata rows, 99 related sources and 20 MiB total, with truncation. Descriptors expose at most 50 snapshots, 100 duplicate groups and 20 versions per group. Unready snapshot sources explicitly make context partial.

## Consequences

Results return actual commit/policy. Repeated sync no longer introduces duplicate-path compiler contexts. Limits can reject a context whose current file lies outside the inspected metadata window. Compiler identity remains static; this adds neither dependency installation nor runtime/build execution. Formal graph writes stay human-only.
