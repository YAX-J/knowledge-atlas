# ADR 0010: Explainable hybrid retrieval with one-hop graph signals

[简体中文](0010-explainable-hybrid-graph-retrieval.zh-CN.md)

- Status: Accepted
- Date: 2026-10-18

## Decision

Add `mode=hybrid` to the existing project search endpoint. It combines three bounded, project-scoped signals over visible formal entities:

- keyword: the existing deterministic keyword score, normalized by the highest keyword score in the candidate pool;
- vector: cosine similarity clamped to the `0..1` contribution range;
- graph: the strongest visible one-hop relationship from another keyword/vector seed, weighted by that seed's strongest normalized retrieval signal and the relationship confidence.

The final score is `0.3 * keyword + 0.4 * vector + 0.3 * graph`. Keyword and vector retrieval each contribute at most 100 seeds. Graph expansion reads at most 500 visible relationships and respects user, project, type, status, and validity-time boundaries. A graph-only neighbor may enter the result set.

Hybrid responses expose the fixed weights, normalized keyword/vector components, graph score, final score, and up to three relationship explanations per hit. They retain source evidence and stable score/name/UUID ordering. The operation is read-only but requires the same explicitly built semantic index and embedding-provider configuration as vector search.

## Consequences

- Ranking can be inspected and reproduced without exposing model reasoning.
- Archived, out-of-time, cross-project, or otherwise invisible relationships cannot affect graph scores.
- Candidate and relationship limits bound query cost, but they are not a global exhaustive graph ranking.
- Fixed weights are a baseline for experiments, not a claim that they are optimal.
- This decision does not implement question answering, multi-hop graph traversal, reranking, entity disambiguation, or automatic index rebuilding.
