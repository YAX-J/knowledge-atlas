# ADR 0081 Optional Neo4j project graph snapshots

[简体中文](0081-neo4j-project-projection.zh-CN.md)

Accepted on 2026-11-13. Verified locally with Neo4j Desktop and PostgreSQL.

PostgreSQL remains authoritative for formal knowledge, evidence, review, identity, and temporal history. The default graph and search endpoints continue to use PostgreSQL and pgvector. This decision updates the Neo4j deferral in [ADR 0005](0005-postgresql-only-storage.md) for an optional, rebuildable graph snapshot.

An explicit per-project sync reads the formal graph visible at `valid_at` (defaulting to the sync time). It reuses PostgreSQL visibility, effective intervals, canonical endpoints, and evidence counts. A project lock serializes projection operations with formal graph updates. The Neo4j data transaction replaces that scope's previous snapshot and records its effective time atomically. The API rejects snapshots exceeding 5,000 nodes or 20,000 relationships before writing snapshot data. Snapshots can be rebuilt by repeating the sync.

Neo4j uses `KnowledgeEntity` nodes with the existing unique business UUID constraint. App-owned snapshot nodes also use `KAProjectionEntity`. Directed `KA_RELATIONSHIP` edges carry the formal relationship UUID and domain `type`. Snapshot rows are scoped by project and user. The optional read endpoint runs bounded Cypher neighborhood queries against the stored snapshot and reports its effective time. Each refresh replaces the previous snapshot, including when the operator selects an earlier time.

Configure Neo4j separately from PostgreSQL. The standalone connection check and snapshot endpoints surface connection failures. Core API readiness depends on PostgreSQL and its schema. Refresh is explicit after knowledge changes. Neo4j Desktop can be used for local validation without a PostgreSQL migration. See the [setup guide](../DEVELOPMENT_SETUP.md) for configuration and commands.

Local verification used Neo4j 2026.10.2. The health endpoint returned 200, two syncs of the existing `test` project each returned 7 nodes and 2 relationships, and uncentered, one-hop, and two-hop reads matched PostgreSQL at the snapshot time. The backend regression suite reported 1,113 passed, 13 skipped, and 95.49% coverage.
