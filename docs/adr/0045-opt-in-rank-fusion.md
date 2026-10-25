# ADR 0045: Opt-in rank fusion and online evidence allocation

[简体中文](0045-opt-in-rank-fusion.zh-CN.md)

Status: Accepted

Date: 2026-10-25

## Decision

Add explicit `mode=rrf`, protocol `bm25-vector-rrf-v1`, alongside unchanged keyword/BM25/vector/fixed-hybrid retrieval. Use the same project, user, type and effective timestamp for both branches. Each branch contributes at most 100 entities. Sum `1 / (60 + rank)` for each branch containing an entity; ties sort by name and UUID. Preserve raw scores, branch ranks, exact evidence, lexical scan limits, index counts and truncation. Do not add graph-only neighbors or interpret ranking scores as answer confidence.

RRF requires local embedding configuration validation. An empty matching index skips the provider and retains lexical hits; provider failures still surface. The public search default stays keyword. Questions accept `retrieval_mode=hybrid|rrf|vector|bm25`, default hybrid. BM25 requires no embedding calls, while answer generation still requires the answer provider when evidence exists.

Online questions allocate evidence round-robin across the first five entities, at most twelve distinct passages. Deduplicate only identical `(source_id, chunk_id, start_line, end_line, quote)` keys, retaining the first canonical evidence ID and its entity attribution. Distinct sources, locations and versions remain separate. All model citations must refer to canonical IDs actually sent. Report selected/duplicate passage counts and truncation. No authoritative evidence or knowledge is rewritten.

## Consequences

Users can compare rank fusion with existing strategies without replacing historical protocols. Existing evaluation output directories and `line-evidence-v2` scoring stay unchanged; the experiment runner may explicitly run RRF with embedding authorization and a fresh output directory. Its historical evidence expansion/answer replay is not an end-to-end assessment of the new online passage allocation.

New behavior is covered by provider-stubbed scope, time, rank, no-call and citation tests. No new paid-provider quality experiment or general improvement claim accompanies this decision. RRF may still rank irrelevant passages; raw-source retrieval, calibrated answerability, merging entities and undo remain outside this change.
