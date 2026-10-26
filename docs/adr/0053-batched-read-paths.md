# ADR 0053: Projected source lists and batched search evidence

Status: Accepted · Date: 2026-10-26

[简体中文](0053-batched-read-paths.zh-CN.md)

## Decision

Measure native read paths before optimizing. Source pagination selects only list fields, with raiseload on omitted columns; a scoped row_number partition selects one latest parsing task per source, preserving created_at/ID ordering. Source detail and parsing continue to load original content when needed.

Search modes share graph.evidence_for_records: one homogeneous user/project/owner-kind batch, scoped joins to sources/chunks/repositories, and one batched Git provenance resolution. Preserve per-owner evidence ordering, exact IDs/quotes/line URLs, existing ranking, limits, response schemas and evidence counts. Single-record details retain the wrapper. RRF has bounded lexical and vector-only batches rather than one read per entity.

## Consequences

The native 100-source/20-task fixture records query counts, elapsed time and Python allocation peaks in [versioned measurements](../../evaluation/performance/2026-10-26-read-paths/README.md). All normalized response fingerprints match. This measures local service work, not HTTP latency, RSS, database memory or representative production capacity. No new index, cache, provider call or ranking change is justified by these results. BM25 retains its bounded scan; large-corpus ranking remains separate work.

Run `python -m scripts.benchmark_reads --output ../output/reads.json` from backend with native PostgreSQL/pgvector and CREATE SCHEMA. It migrates a random private schema, proves physical ownership before synthetic fixture writes, uses normal review/promotion and removes only its own schema; application tables and migration marker must remain unchanged.
