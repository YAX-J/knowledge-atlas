# ADR 0044: Add a bounded offline lexical baseline

[简体中文](0044-bounded-offline-bm25-search.zh-CN.md)

- Status: Accepted
- Date: 2026-10-25
- Extends ADR 0008 without changing its literal keyword semantics

## Context

The frozen Chinese-question experiment has zero keyword recall because whitespace splitting and AND matching treat whole question fragments as literal terms. The fixed hybrid baseline also underperforms vector retrieval; that alone does not justify tuning against the same 40 questions or silently replacing historical results.

## Decision

Add explicit `mode=bm25`, keeping `keyword` as default and leaving weighted hybrid/questions unchanged. Use a deterministic pure-Python tokenizer: Han characters and adjacent bigrams, casefolded Unicode words, identifiers and their punctuation-delimited parts. Apply corpus-local Okapi BM25 to concatenated entity name, summary and accessible evidence, with no field boosts, learned stop words or gold-answer input. Use positive IDF `log(1 + (N-df+0.5)/(df+0.5))`, `k1=1.2`, `b=0.75`; see the primary [Lucene BM25 documentation](https://lucene.apache.org/core/7_6_0/core/org/apache/lucene/search/similarities/BM25Similarity.html). Tokenization is an application choice, not full linguistic segmentation or equivalence to Lucene's analyzer.

Recompute only within the current user/project/type/time-visible formal entities. Scan at most 1000 entities, 5000 scoped evidence rows (2000 characters per quote), and 4000 ranking characters per entity. Return `lexical` metadata and explicit truncation reasons. Rank by score, name, UUID; prefer matching evidence, returning unchanged exact quotes and source links. Scores are not confidence or answerability. No network, model, vector index, persistent lexical index, graph mutation or migration is added. Large corpora require a future measured indexing decision.

Before semantic query embedding, count the matching index and return an empty vector result if it is empty. Validate configuration locally so missing-provider and wrong-dimension errors stay compatible. A configured empty hybrid index can still return literal/graph matches without a query-embedding request; this is not a general provider-failure fallback.

## Consequences and acceptance

The frontend adds an explicitly free BM25 option, distinct scan/index messages and a busy-submit guard. The runner accepts BM25 without model authorization, records its protocol and lexical diagnostics, and rejects unsupported/empty mode lists. Historical results and scoring protocol stay unchanged.

The [development diagnostic](../../evaluation/results/2026-10-25-bm25/README.md) uses exactly the existing corpus/graph/index fingerprints and zero provider requests. It is not held-out validation; code-location and unanswerable results are reported even when poor. Native PostgreSQL and SQLite tests verify scoping, temporal/archival filters, formula, limits and zero-call empty-index behavior. Further fusion tuning needs an independent evaluation plan.
