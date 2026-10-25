# ADR 0051: Optional source-aware lexical retrieval

[简体中文](0051-source-aware-lexical-retrieval.zh-CN.md)

Status: Accepted

Date: 2026-10-25

## Decision

Add opt-in `mode=bm25_source` and question `retrieval_mode=bm25_source`. Protocol `mixed-bm25-source-v1` adds evidence-source original filename, relative path and chunk heading text as the `provenance` field, before quote text in the existing per-entity text budget. Tokenization, BM25 parameters and all entity/evidence/time/tenant limits are unchanged. Only sources reached through scoped formal evidence participate; unreviewed source/code structure is not answer knowledge. Metadata-only hits still return original exact evidence and canonical IDs. Heading contributions are limited to 512 characters, with truncation reported.

Keep `bm25`, keyword, fixed hybrid, vector, RRF and all defaults unchanged. New-mode experiments receive a distinct protocol and new output directory. Source paths are location context, not evidence that an arbitrary semantic claim is true. Citation-ID validation, evidence budgets and explicit insufficient-evidence responses remain in force.

## Consequences

Users can explicitly search reviewed knowledge by code file/path or heading without embeddings. Nine new isolated functional cases exercise location, absent queries and a simulated refusal for misleading word overlap; they are development regressions, not a blind or representative quality benchmark. On the old 40-case development set both modes achieve 74.49% Recall@5; the new mode is not promoted to default or claimed generally superior. No new model calls or persisted formal objects are introduced.
