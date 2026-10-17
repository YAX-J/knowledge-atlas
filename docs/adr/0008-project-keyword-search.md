# ADR 0008 Evidence-backed project keyword search

[简体中文](0008-project-keyword-search.zh-CN.md)

- Status: Accepted
- Date: 2026-10-17

## Decision

Start retrieval with read-only keyword search over formal entities in the current user's active project. Search names, summaries, and scoped evidence quotes. Pending/rejected candidates and relationships are not search results; relationship navigation remains available from entity details and neighborhoods. Apply the graph's archive and validity-time visibility rules.

Use SQLAlchemy parameterized, case-insensitive substring matching with literal wildcard escaping. Split 1–200 characters into at most eight whitespace-separated terms, deduplicate terms, and require every term to match at least one field. Chinese phrases remain literal substrings; no tokenizer, stemming, synonyms, or semantic interpretation is provided.

Rank with a reproducible integer keyword score: 50 for a case-insensitive exact full-query name match, plus 10/3/1 per distinct term matching name/summary/evidence. A term counts once per field regardless of quote count. Order ties by name then business UUID. This is a ranking score, not confidence. Return `top_k` (1–50, default 10), a truncation flag, matched fields, and up to three evidence records per hit, prioritizing matching quotes. All fields retain user/project boundaries.

The API accepts `mode=keyword` only. Unsupported vector/hybrid modes return 422. The project graph has its own search form, separate from demo-header search and graph viewport filters; selecting a hit opens entity details, loading its neighborhood if it lies outside the current canvas. Request counters discard results after project changes, clearing, or newer searches. Search never calls a model or mutates records.

## Consequences

No migration or dependency is added; head remains `20261017_0005`. Substring queries may scan the project's records and are intended for the current small corpus. Indexing/full-text tokenization, vector embeddings, graph-score fusion, relationship retrieval, and real evidence-grounded answers remain later slices. Native PostgreSQL checks validate SQL behavior; simulated extraction does not establish real model quality.
