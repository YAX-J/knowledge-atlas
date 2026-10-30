# Ordered read optimization measurements, 2026-10-30

[简体中文](README.zh-CN.md)

These are new synthetic local measurements, not held-out answer quality. Historical results are untouched. Every native fixture uses an explicitly migrated, physically owned temporary schema and is removed afterwards; the application revision remains20261029_0019. No providers were called.

- [Symbol cache](symbol-cache.json):50 deterministic Java/Python sources,30 declarations each, cold parser/cache call followed by3 warm repetitions in one process. Output hashes agree;150 warm accesses all hit. Cold326.806 ms, warm0.538–0.618 ms. Peak traced Python allocations584957 versus1717 bytes; retained accounted cache metadata871050 bytes. Accounted bytes are a conservative budget, not actual process memory. This excludes database, source loading, HTTP and cold server startup.
- [History JSON](history-summary.json): synthetic256-event envelopes with3800-character answer text.10 rows:355586→2676 bytes;50 rows:1777746→13196 bytes. IDs/order agree. This measures uncompressed serialized response bytes, not network speed or compression, and is not representative of every real page.
- [Lexical v2](lexical/run.json):1000/10000 synthetic candidates confirmed through ordinary review, one source/chunk/exact evidence per entity. Production limits/ranking are unchanged. One warm-up per query/mode is excluded;3 fresh-session samples include tracemalloc and response serialization. All repeated output hashes agree; scanned_count equals corpus size. A3-sample median does not establish p95/SLA. Python allocations exclude PostgreSQL memory and RSS.

| Entities | Mode | Query | Median ms | Peak Python bytes | SELECTs |
| --- | --- | --- | --- | --- | --- |
| 1000 | bm25 | PostgreSQL | 496.696 | 1399919 | 26 |
| 1000 | bm25 | record 999 | 419.167 | 1324742 | 26 |
| 1000 | bm25_source | PostgreSQL | 480.218 | 1330277 | 26 |
| 1000 | bm25_source | record 999 | 365.297 | 1335005 | 26 |
| 10000 | bm25 | PostgreSQL | 3357.603 | 7231583 | 161 |
| 10000 | bm25 | record 9999 | 3367.718 | 7139972 | 161 |
| 10000 | bm25_source | PostgreSQL | 3968.589 | 7177825 | 161 |
| 10000 | bm25_source | record 9999 | 3869.653 | 7145658 | 161 |

Reproduce from backend with new output paths (existing output is not overwritten):

```powershell
.\.venv\Scripts\python.exe -m scripts.benchmark_symbol_cache --output ../output/new-measurement/symbol-cache.json
.\.venv\Scripts\python.exe -m scripts.benchmark_agent_history --output ../output/new-measurement/history-summary.json
.\.venv\Scripts\python.exe -m scripts.benchmark_lexical_v2 --output ../output/new-measurement/lexical --repeats 3
```

Interpretation: repeated parse reuse and payload reduction are demonstrated on these fixtures. Full lexical scanning still costs more at10k than1k; no new index/cache/ranking choice is justified by these small synthetic measurements alone. Real document distributions, process memory and end-to-end latency require separate measurements. See [ADR0071](../../../docs/adr/0071-bounded-read-caches-and-summaries.md).
