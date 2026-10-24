# ADR 0042: Replay curated synthetic evaluation projects through review services

[简体中文](0042-reproducible-curated-evaluation-projects.zh-CN.md)

Status: Accepted

Date: 2026-10-24

## Context

Stage 6 has a frozen corpus/scorer, but manual preparation is difficult to reproduce. Current-time promotions cannot answer historical cases, and a corpus fingerprint alone does not freeze the reviewed graph or vector index.

## Decision

- Add a corpus-only curated annotation file and a standalone `scripts.prepare_evaluation` command. Explicit operator acceptance, a new project UUID, a new report directory and a development/test/evaluation environment are required.
- Reuse ordinary source creation, parsing, pending candidates, `resolve_review`/`promote_candidate` and reviewed evolution. No formal record is created directly by the script, no model runs and no application API changes.
- Replay the synthetic availability clock only around formal promotion inside the standalone process. Restore it on success/failure; never import/run this command in an API/Worker process. Candidate metadata and preparation reports mark synthetic history and annotation provenance. This is fixture replay, not a claimed historical human review.
- Wrap service commits in savepoints inside one outer transaction. Refuse existing projects; any failure rolls back the whole new project. Validate all paths, source coverage, IDs, evidence lines, local relation endpoints, historical availability and replacement chronology before writing, then revalidate the fixture before committing.
- Fingerprint actual knowledge/evidence/evolution and the vector index, normalizing business UUIDs across independent prepared projects. Record/recheck these in experiment runs; graph/index changes invalidate a run.
- Add `scripts.run_baselines` for one explicit index rebuild followed by keyword/vector/hybrid retrieval, never answer generation. Record attempted/successful/failed embedding calls and character/text counts, diagnostics and comparison tables. Default batches contain ten texts and may be overridden for provider limits. Billing values remain unknown unless actually supplied.
- Release dataset `1.0.1` to remove future evidence from `temporal-006`. Scoring protocol `line-evidence-v2` tolerates formal-schema outer whitespace trimming while requiring equal source, lines and interior text.

## Consequences

The same synthetic reviewed graph supports repeatable three-mode comparison and real PostgreSQL acceptance without introducing a production backdating mechanism. Corpus annotations are accepted by the operator, not evidence of automatic extraction quality. Synthetic data, one provider/model, fixed retrieval weights and whitespace-based Chinese keyword matching limit conclusions; answer quality, real repository quality, tool-calling Agents and human grading remain separate work.

## Verification

Agent executor retained from the user's earlier choice. Commands: `python -m scripts.prepare_evaluation --dataset ../evaluation --validate-only`, focused preparation/evaluation/review tests, full `pytest`, disposable native `python -m scripts.verify_native`, and `git diff --check`. The user separately allowed this round's real embedding calls and kept DeepSeek calls deferred. Results are recorded with the completed change.

Completed on 2026-10-24: full backend suite 575 passed / 5 explicitly skipped, one existing Starlette warning; disposable PostgreSQL 17.10 / pgvector 0.8.7 migration/review/initialization acceptance passed and removed its schema without changing the application migration marker. Real preparation produced the documented counts. One 85-request embedding run completed all 120 retrieval predictions, with zero answer calls; raw predictions/diagnostics and offline rescoring tests are versioned under `evaluation/results/2026-10-24-v101/`. Vector Recall@5 was 0.9806, hybrid 0.6602 and keyword 0.0000. A failed initial 32-text batch and one successful single-text diagnostic are reported separately. No frontend change or browser validation was needed.
