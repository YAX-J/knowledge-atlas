# ADR 0007 Promote confirmed candidates into the PostgreSQL graph

[简体中文](0007-confirmed-postgresql-graph.zh-CN.md)

- Status: Accepted
- Date: 2026-10-17

## Decision

Extend ADR 0006: confirmation now promotes candidates to formal PostgreSQL entities, relationships, and evidence in the same transaction as review state and its audit event. Revalidate evidence and scoped endpoints at promotion. Stable UUIDs and unique candidate references make repeats idempotent. Replaying an unchanged confirmation also promotes legacy confirmed candidates without repeating model calls or audit events; relationships may promote their already-confirmed endpoints in that transaction.

Use scoped composite foreign keys for relationship endpoints and evidence ownership. Formal records preserve candidate provenance, confidence, status, and validity properties. Initial validity begins at promotion; historical semantic dating and automatic SUPERSEDES state transitions remain future work. SUPERSEDES keeps its new-to-old direction. No entity merge or cross-batch deduplication is inferred.

Graph reads are read-only, scoped to active projects and users, and bounded by node/edge limits. Support optional centers, one/two-hop neighborhoods in either direction, entity-type filtering, and validity-time filtering. The frontend owns layout and shows real project graph data separately from the existing demo. Entity and relationship details expose original filenames, chunk references, quotes, and server-calculated lines. No real question-answer behavior is added.

## Consequences

Migration `20261017_0005` adds graph tables without changing existing candidates. Legacy confirmation can be replayed explicitly from the review UI. Downgrade drops formal graph records/evidence while preserving sources, candidates, and review events; promotion can rebuild them. Formal evidence prevents deletion of referenced chunks, so destructive re-parsing is not supported. PostgreSQL 17.10 disposable-schema checks passed migration upgrade/downgrade/re-upgrade, evidence reads, and concurrent identical confirmations. Browser verification uses isolated SQLite and simulated extraction; real model quality and native-database browser acceptance remain outstanding.
