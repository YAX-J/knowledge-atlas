# Native read-path development measurement — 2026-10-26

[简体中文](README.zh-CN.md)

Baseline application commit: `1aeb4b3`. Baseline was measured before production edits, using the same new `scripts.benchmark_reads` driver. After measurement uses ADR 0053. Both ran PostgreSQL 17.10 / pgvector 0.8.7 with 100 synthetic sources (128 KiB body padding each), 20 parsing tasks per source (4 KiB synthetic error padding each), and 100 candidates confirmed through the normal review/promotion flow. No model/embedding/network providers. A fresh session per sample, three samples per operation; timings include service and model serialization, exclude connection acquisition. Python tracemalloc allocation peak is not RSS or server memory. SQL statement capture overhead is included. Caches/warm-up and local noise affect timings; raw samples are retained.

| Operation | Queries before → after | Median ms before → after | Max Python peak bytes before → after |
| --- | --- | --- | --- |
| Sources page 20 | 8 → 8 | 47.124 → 19.566 | 5,767,430 → 869,883 |
| Sources page 100 | 8 → 8 | 182.924 → 46.385 | 27,433,069 → 868,824 |
| Keyword top 50 | 253 → 8 | 407.964 → 45.874 | 1,020,038 → 734,609 |
| BM25 top 50 | 255 → 10 | 423.279 → 66.280 | 1,269,886 → 978,869 |
| BM25 source top 50 | 255 → 10 | 423.664 → 73.029 | 1,280,628 → 992,780 |

All 11 operation output hashes match after excluding only formal entity fixture timestamps. IDs, ranks, evidence, scores, truncation and source/task list output remain identical. Top-1 timings did not improve consistently; no universal speedup claim. Only bounded local synthetic read paths were measured, not large-corpus capacity, provider latency, HTTP, p95, or model quality. BM25 still scans at most 1000 eligible entities and its text/evidence budgets remain unchanged. Vector/hybrid/RRF evidence reads use the same batching; their provider timing is not represented here.

Reproduce the current implementation from `backend/`: `.\.venv\Scripts\python.exe -m scripts.benchmark_reads --output ../output/read-benchmark.json`. Requires native PostgreSQL/pgvector and CREATE SCHEMA; driver proves physical table ownership, removes only its generated schema and verifies the application migration marker/synthetic project absence. Preserve these versioned files; write new runs elsewhere.
