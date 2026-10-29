# ADR 0060 Schema-aware readiness

[简体中文](0060-schema-aware-readiness.zh-CN.md)

- Status: Accepted
- Date: 2026-10-29

## Decision

`/health/live` stays process-only. `/health/ready` checks database connectivity, a physically owned Alembic version table at the exact expected head, the six workspace tables and snapshot scan-state column. Unmigrated, behind, falsely stamped or incomplete schemas return 503 with safe dependency detail. The expected head is regression-checked against Alembic scripts; private search paths must own their marker rather than fall through to public.

Back up and verify isolated schema recovery before upgrading an existing application database. Never auto-upgrade at health-check/startup time. The accepted application upgrade is 0017→0018 with canonical UTC comparison of all 18 pre-existing business tables; the backup remains local and ignored.

## Consequences

Connectivity alone no longer implies that routes can run. This is a structural readiness guard, not exhaustive data-integrity verification. Future migrations must update the guard and its tests. Provider availability is not part of free readiness.
