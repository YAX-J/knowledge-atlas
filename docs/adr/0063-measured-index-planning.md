# ADR 0063 Measured index planning

[简体中文](0063-measured-index-planning.zh-CN.md)

- Status: Accepted
- Date: 2026-10-29

## Decision

Read original-owner evidence in batches of 500 entities, projecting existing embedding identity/model/dimensions/hash without vector bodies. Return pending UUID/text/hash tuples so committing the read transaction does not expire ORM owners and trigger one extra select per item. Preserve evidence UUID order and original-owner hashing so identity merges cannot leak future facts into historical vectors. Transport batching, reuse and explicit index-operation ownership remain unchanged.

Use reviewed synthetic 1k/10k fixtures in physically owned temporary native schemas, 20 warm samples per operation, exact pre/post plan fingerprints, SQL/p95/Python allocation accounting and cold-index request estimates. Network providers are blocked. Keep measurements/versioned reports separate from answer-quality experiments. The v3 public document holdout is frozen separately and never used for ranking tuning.

## Consequences

Planning query count is O(N/500), while entity/pending memory remains O(N). Measurements exclude provider latency/vector persistence and do not prove production capacity. BM25 retains its explicit 1000-entity scan window. No new cache or ANN index is justified without representative temporal/canonical vector measurements; do not infer monetary cost from character counts.
