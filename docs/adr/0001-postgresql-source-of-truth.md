# ADR 0001 PostgreSQL as the source of truth

[简体中文](0001-postgresql-source-of-truth.zh-CN.md)

- Status: Superseded by [ADR 0005](0005-postgresql-only-storage.md)
- Date: 2026-10-17

This record preserves the original dual-database design. ADR 0005 retains PostgreSQL as the source of truth and defers Neo4j; the projection requirements below are historical, not current implementation requirements.

## Context

Knowledge Atlas plans to use PostgreSQL and pgvector for business data and vector retrieval, and Neo4j for graph traversal. Allowing both databases to be independently writable sources of truth would create inconsistent confirmation status, evidence links, temporal state, and deletion behavior.

## Decision

PostgreSQL will be the authoritative store for business state, source material, review status, stable identifiers, and synchronization metadata.

Neo4j will contain a rebuildable projection optimized for relationship traversal. Graph nodes and relationships will use stable business UUIDs rather than Neo4j internal IDs. A confirmed PostgreSQL transaction will produce an idempotent graph-projection operation. The first implementation may use direct application synchronization, but it must preserve a path to an Outbox-based worker.

## Consequences

- Business state has one authoritative location.
- Neo4j can be rebuilt after corruption or schema changes.
- The system must track projection state, retries, and errors.
- Graph reads may temporarily lag behind PostgreSQL writes.
- API responses must handle projection lag explicitly when it affects the user.

## Alternatives considered

### Neo4j as the only database

Rejected because file metadata, tasks, review workflows, vector storage, and transactional business records are better served by PostgreSQL.

### Dual authoritative writes

Rejected because distributed consistency and recovery would add unnecessary risk to a graduation-project scope.

### PostgreSQL graph queries only

Not selected for the target architecture because Neo4j makes multi-hop relationship queries and graph demonstrations clearer. It remains a fallback if operational complexity threatens the minimum viable product.
