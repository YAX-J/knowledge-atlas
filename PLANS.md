# Knowledge Atlas implementation plan

Latest 2026-10-31: steps1–2 complete: server-derived v3 aggregate support and independent synthetic development/legacy compatibility checks. See [ADR0075](docs/adr/0075-server-derived-answer-support.md) and [development cases](evaluation/development/claim-support-v3/README.md). No live calls or v3 quality measurements. [Prior457 Clef judgments](evaluation/results/2026-10-31-holdout-v3-clef-run1/REPORT.md) describe historical v2 only; frozen failures/scores/inputs/ledgers remain unchanged, human0%. All prior grants are exhausted. Release freezing and final thesis revisions remain pending.

Offline judging now supports OpenRouter Jev, direct TypeSafe Jev and native CF adapters, with human grading coverage0%. OpenRouter Decisions API and release/snapshot validation are implemented with zero-call preflight; live compatibility/quality remain unverified. See [OpenRouter setup](docs/OPENROUTER_EVALUATION.md) and [ADR0073](docs/adr/0073-openrouter-jev-evaluation.md). Earlier read optimizations remain in ADR0071.

[ADR 0075](docs/adr/0075-server-derived-answer-support.md) implements `evidence-claims-v3`: providers return only confidence, claims and missing_information; the backend derives API supported from all claim statuses. Citation attribution, missing information, budgets and project scope stay strict. v2 and flat history read/replay saved values without recomputation or provider calls; v2 is never a new-output fallback. Independent fictional development cases check structure/compatibility, not live v3 quality. Frozen v2 experiments/ledgers/scores and schema head `20261029_0019` remain unchanged; human coverage0%.

[简体中文](PLANS.zh-CN.md)

## Project Agent development proposal

M1–M2 are implemented and locally verified on feat/project-agent: five scoped read-only tools, typed reports, asynchronous202 submissions, a separate runner, durable attempts/checkpoints/artifacts, cancellation and explicit bound continuation. Business/source head20261031_0021 followed verified backups/restores and preserved content. See [current M2](docs/PROJECT_ASSISTANT_M2.md) and [ADR0077](docs/adr/0077-durable-assistant-execution.md). M3–M5 remain planned; frozen experiments and grants are unchanged, with zero live calls.

## Multi-agent extension

The approved single-project refactor is implemented: three registered agents, two explicit LangGraph pipelines, shared scope/budgets, persistent run history, read-before-retry and a human-review checkpoint. Migration head/application are `20261029_0019`. See [architecture and contracts](docs/MULTI_AGENT.md). Existing evaluation limits below remain.

## Current scope

The user's ordered P0/P1/P2 optimization is implemented in code. Acceptance evidence and limits live in [the current report](docs/OPTIMIZATION_20261029.md). Historical phase/checkpoint prose is preserved in [the archive](docs/archive/pre-optimization-20261029/PLANS.md); it is not the current capability specification.

| Priority | Result |
| --- | --- |
| P0 | Schema-aware readiness, verified backup/schema restore, application upgrade to `20261026_0018`, and a provider-stubbed native workflow |
| P1 | Immutable commit/local version code context; normalized identity bounds and merge-chain regressions; critical frontend integration checks |
| P1 evaluation | Separate 7-document/24-question holdout-v3 frozen before provider use; real blind grading explicitly deferred by the user |
| P2 navigation | Restorable project/source/entity/relationship/time/conversation URLs; shorter graph task sections |
| P2 performance | Native 1k/10k reviewed synthetic fixtures; before/after plan fingerprints, SQL counts, p95, Python memory and request estimates; evidence batches of 500 |
| P2 maintenance | Evidence navigation, snapshots and evolution composables; current documentation separated from historical checkpoints |

## External work still pending

Keep historical80-answer whole-answer grading separate from91 new claim-level exports. The457 jobs completed with human coverage0%. Retain full/subset denominators, failures and uncertainty; all methods have20 correct labels on22 shared valid cases, so defaults are unchanged. Markdown thesis/demo drafts are ready, without editing a Word thesis or publishing.

Private repository acceptance, privileged fresh-database recovery, Docker and remote CI need their actual environments. They remain explicit limits, not hidden assumptions about completion.

## Planning rules

ADR 0068 completes explicit collaboration-page retrieval/time/code selection, context-fenced read-only metadata loading, draft previews and saved scope projection. Preserve the BM25 default and same-UUID replay behavior; historical questions exclude current code. Focused/full/native/frontend/browser acceptance is recorded in that ADR; genuine answer-quality evaluation remains separate.

The next reliability slice (ADR 0067) persists per-event call reservations and validated step checkpoints, fences/renews active executions and keeps partials on failure. The user retained Agent verification; focused/full/native/frontend/browser results are recorded in the ADR. Execution remains synchronous and interrupted tasks are read-only on replay; automatic node continuation is outside this change.

The 2026-10-30 lexical coverage change replaces the 1k window with 200-entity keyset batches and a 50k explicit scan budget, shared global BM25 statistics, bounded per-entity evidence and v2 protocol metadata (ADR 0066). Regression/acceptance results are recorded in that ADR after execution; historical experiments and the holdout remain unchanged.

Preserve evidence, user/project scope, explicit human graph writes and additive migration safety. Future work should measure the v2 batch scan and representative semantic/vector workloads before index/caching decisions. The synchronous scan is not a resumable cross-request job. Current warm synthetic results do not establish production capacity. No push/deployment or new major phase is authorized by this plan alone.
