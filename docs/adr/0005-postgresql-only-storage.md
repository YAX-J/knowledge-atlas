# ADR 0005 Use PostgreSQL only and defer Neo4j

[简体中文](0005-postgresql-only-storage.zh-CN.md)

- Status: Accepted
- Date: 2026-10-17
- Supersedes: [ADR 0001](0001-postgresql-source-of-truth.md)

## Context

The user wants native local development without Docker and already has PostgreSQL. Neo4j currently contributes only configuration, a driver dependency, and readiness checks; no graph data or business graph queries have been implemented. Maintaining another database and a projection pipeline adds work before the Markdown-to-evidence-answer flow is complete.

## Decision

Use PostgreSQL as the only current database and the source of truth. Retain pgvector for planned vector retrieval. Remove Neo4j from package dependencies, settings, environment examples, readiness checks, and optional Compose services and volume declarations.

Implement future graph nodes, relationships, evidence associations, review status, and temporal state in PostgreSQL. Preserve the knowledge model, stable business UUIDs, `user_id`/`project_id` boundaries, evidence traceability, and `new knowledge -[:SUPERSEDES]-> old knowledge` direction. These tables and real graph APIs remain unimplemented in this change.

Use joins for direct relationships and consider recursive queries for bounded traversal. Include scope and temporal filters, cycle protection, depth/result limits, and indexes appropriate to measured queries. Commit confirmed knowledge and its evidence/review state in one transaction.

Neo4j may be reconsidered through a new ADR if measured query complexity, performance, or graph-algorithm needs justify a separate graph database. PostgreSQL would remain authoritative and a graph projection would use the same stable UUIDs. No dormant driver, feature flag, or synchronization layer is retained now.

## Consequences

- Native development and acceptance require only PostgreSQL with pgvector; Docker remains optional.
- Readiness reports PostgreSQL only, returning HTTP 200 when connected and HTTP 503 on connection failure. This does not validate migrations or pgvector availability.
- No application graph data needs migration because graph persistence has not been implemented.
- Existing local `NEO4J_*` environment entries are ignored and can be removed. Removing Compose volume declarations does not delete any existing database volumes or installations.
- Graph querying requires SQL design and performance validation. This decision does not claim equivalence to a specialized graph database for arbitrary traversals.
- Real graph display, extraction, retrieval, and Agent answers remain future work.

## Alternatives considered

### Keep Neo4j mandatory or behind a disabled health-check flag

Deferred because it retains setup work or unused dependencies before any business capability uses them.

### Replace Neo4j with another graph database or extension

Deferred because it introduces another installation and compatibility boundary without a demonstrated requirement.
