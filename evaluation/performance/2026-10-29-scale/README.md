# Native 1k/10k read and index-planning measurement

[简体中文](README.zh-CN.md)

Run on local PostgreSQL 17.10 / pgvector 0.8.7, 2026-10-29. [Raw samples](native-scale-v1.json) include 20 warm measured calls plus one excluded warm-up per operation. Each size owns and removes a migrated disposable schema. Candidates use the ordinary explicit review/promotion service; synthetic evidence is one short source/chunk per entity. No provider request, embedding or user-data write occurred.

| Entities | Plan SQL before → after | Plan p95 ms before → after | Peak Python MiB before → after |
| --- | --- | --- | --- |
| 1,000 | 1,002 → 4 | 837.236 → 103.809 | 2.69 → 2.78 |
| 10,000 | 10,002 → 22 | 8,914.231 → 1,033.329 | 23.63 → 23.67 |

Pre/post output fingerprints match at each size: same eligible count and ordered pending UUID/text/hash tuples. Evidence now uses batches of 500; existing embeddings use metadata projection. Memory remains linear and was not reduced by this measurement.

| Entities | Keyword p95 ms / SQL | BM25 p95 ms / SQL | Source-aware BM25 p95 ms / SQL |
| --- | --- | --- | --- |
| 1,000 | 1,452.514 /10 | 343.167 /13 | 399.234 /13 |
| 10,000 | 485.218 /10 | 616.456 /13 | 641.889 /13 |

These are instrumented local samples with Python tracing, OS/database cache and concurrent machine activity, not cold-cache SLA or a monotonic growth claim. Connection acquisition, network/provider time and vector persistence are excluded. Memory is tracemalloc peak, not process RSS or server memory. Exact/top-10 queries use production scope and limits. BM25 at 10k still scans at most 1k entities and reports truncation; this report makes no full-corpus recall claim. Representative temporal/canonical vector measurements are needed before an ANN index; a result cache would require evidence/time/identity invalidation. Neither is justified by these data alone.

At batch size 32, a completely missing index would require **32** embedding requests for 1k entities or **313** for 10k, covering 102,780 /1,056,780 input characters in this fixture. These are hypothetical counts, not permission or paid calls. An unchanged index needs zero requests. No currency amount is estimated without a tokenizer, provider rates and reported usage. Existing authorization remains cumulative 120 model /160 embedding attempts, already 84/61 used; never run a 10k real rebuild under that remaining allowance.

Reproduce from `backend`:

```powershell
.\.venv\Scripts\python.exe -m scripts.benchmark_scale --output ../output/scale-new-run.json --repeats 20
```

The frozen pre-change algorithm is kept only in the benchmark for equivalence/performance comparison. Do not overwrite this result directory with new measurements.
