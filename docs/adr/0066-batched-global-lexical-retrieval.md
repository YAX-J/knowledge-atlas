# ADR 0066 Batched lexical retrieval with global corpus statistics

[简体中文](0066-batched-global-lexical-retrieval.zh-CN.md)

- Status: Accepted
- Date: 2026-10-30
- Supersedes the scan/evidence budgets and protocol identifiers in ADR 0044/0051; the tokenizer, BM25 formula, explicit modes and evidence boundaries remain.

## Decision

Replace the first-1000-entity BM25 window with keyset pagination ordered by name/UUID, 200 projected entities per batch and an explicit 50,000-entity request budget. Preserve user/project/type/effective-time/identity visibility conditions on every batch and final entity read. Count all scanned documents, including empty and unmatched documents, in the shared document count, total token length and query-term document frequencies; score matches only after the scan finishes. Do not score each batch as a separate corpus.

Retain query-term frequencies/length/matched fields only for matching entities. A bounded Top K heap selects final records after global statistics are available. Source bodies are never selected for ranking. Rank evidence with a SQL row-number window partitioned by canonical entity; read at most 32 quotes plus one omission sentinel per entity, each quote at most 2000 characters. Keep 4000 ranking-text characters per entity, field order name/aliases, summary, optional provenance, then evidence. The name/UUID cursor includes repeated names. No provider, formal graph write, persistent search index or migration is added.

Emit `mixed-bm25-v2` / `mixed-bm25-source-v2`. RRF uses v2 BM25, and new evaluation manifests identify it as `bm25-vector-rrf-v2`. Keep old protocol values readable in schemas/types; do not rewrite frozen corpora, experiment outputs or historical scores. Literal keyword and fixed hybrid behavior remain unchanged.

Add `lexical.batch_size`, `evidence_limit_per_entity`, `matched_count` and `results_truncated`. Existing `entity_limit` now reports 50000; `scanned_count` is the accumulated scanned count. `truncated_reasons` continues to report `entity_limit`, `evidence_limit` and `text_limit`; these describe omitted ranking input, independently of a larger matching pool than Top K. The aggregate `truncated` remains their union with output truncation. RRF lexical metadata describes its lexical candidate pool, not the final fused output.

## Consequences

Queries can retrieve the only matching entity after position 1000 without unbounded source-text allocation or per-entity SQL queries. Scan work and compact matching statistics still grow with corpus size; the 50k ceiling and per-entity text/evidence limits can omit relevant input and must remain visible. Pagination is synchronous within a request, not a persisted/resumable search job. Concurrent edits between statements do not acquire a database snapshot or promise repeatable-read isolation. Additional full-text/ANN indexes, cache invalidation, provider experiments and human grading remain separate work. Existing v1 latency/quality numbers cannot be attributed to v2.

## Verification

The user selected Agent execution. Actual results on 2026-10-30:

- Focused lexical/source/retrieval/read-performance/question/evaluation regressions: 55 passed.
- Full backend with `KA_NATIVE_COMPILERS=1`: 730 passed, 7 explicit opt-in external/native cases skipped; application statement coverage 95.18%, above the 90% gate.
- Native PostgreSQL 17.10 / pgvector 0.8.7: 152 passed in the runner-owned schema, including migration upgrade/downgrade/upgrade. The schema was removed; the application's migration marker was unchanged.
- Frontend: 116 tests across 16 files passed, configured statement coverage 68.66% / line coverage 73.42%; type checking and production build passed. No visible UI changed, so no browser walkthrough was required.
- Changed Markdown files: 266 local link targets resolved. Whitespace review passed; frozen evaluation assets were unchanged.

The first sandboxed TestClient run stalled and was stopped; the same venv regressions completed outside the sandbox. The old shared-evidence-budget assertion was replaced by independent per-entity coverage. No real provider calls were made. These results establish correctness/integration, not v2 latency, production capacity or semantic answer quality.
