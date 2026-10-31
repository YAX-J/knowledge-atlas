# Knowledge Atlas implementation plan

2026-10-31: [Historical diagnostics](evaluation/results/2026-10-31-public-v2-diagnostics/REPORT.md) cover 80 answers and the completed historical Clef 214-request run. The [current-system experiment](docs/CURRENT_SYSTEM_EVALUATION.md) adds per-case historical time, claim/input-pool exports, compatible numeric projections and zero-call preflight. Holdout-v3 remains frozen; its prospective four-method upper bounds are96 model/73 embedding calls against historical remaining36/99. Live use is blocked pending explicit additional authorization; this turn makes0 real calls. Human grading remains0%.

Offline judging now supports OpenRouter Jev, direct TypeSafe Jev and native CF adapters, with human grading coverage0%. OpenRouter Decisions API and release/snapshot validation are implemented with zero-call preflight; live compatibility/quality remain unverified. See [OpenRouter setup](docs/OPENROUTER_EVALUATION.md) and [ADR0073](docs/adr/0073-openrouter-jev-evaluation.md). Earlier read optimizations remain in ADR0071.

Claim-level answers are implemented in [ADR 0069](docs/adr/0069-answer-claim-evidence.md): `evidence-claims-v2` binds each supported claim to current scoped evidence, marks insufficient claims separately and supports exact source navigation. The server derives legacy flat fields; old records remain readable without inferred attribution or new provider calls. Structural validation does not establish semantic entailment. Frozen experiments, the 84/61 provider ledger and schema head `20261029_0019` remain unchanged; evaluation uses anonymous model grading with human coverage0%.

[简体中文](PLANS.zh-CN.md)

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

The historical Clef model review is complete for80 old public-v2 answers; it is not current-system or holdout-v3 quality evidence. The user selects anonymous model grading with human coverage0%. OpenRouter Jev, direct TypeSafe and native CF adapters are available. Current holdout preflight is blocked by answer authorization; a new live round and its exact subsequent judge request count require separate approval. Keep v3 frozen and separate from development data; never tune judge prompts, ranking or thresholds against it. Historical human-score fields remain untouched.

Private repository acceptance, privileged fresh-database recovery, Docker and remote CI need their actual environments. They remain explicit limits, not hidden assumptions about completion.

## Planning rules

ADR 0068 completes explicit collaboration-page retrieval/time/code selection, context-fenced read-only metadata loading, draft previews and saved scope projection. Preserve the BM25 default and same-UUID replay behavior; historical questions exclude current code. Focused/full/native/frontend/browser acceptance is recorded in that ADR; genuine answer-quality evaluation remains separate.

The next reliability slice (ADR 0067) persists per-event call reservations and validated step checkpoints, fences/renews active executions and keeps partials on failure. The user retained Agent verification; focused/full/native/frontend/browser results are recorded in the ADR. Execution remains synchronous and interrupted tasks are read-only on replay; automatic node continuation is outside this change.

The 2026-10-30 lexical coverage change replaces the 1k window with 200-entity keyset batches and a 50k explicit scan budget, shared global BM25 statistics, bounded per-entity evidence and v2 protocol metadata (ADR 0066). Regression/acceptance results are recorded in that ADR after execution; historical experiments and the holdout remain unchanged.

Preserve evidence, user/project scope, explicit human graph writes and additive migration safety. Future work should measure the v2 batch scan and representative semantic/vector workloads before index/caching decisions. The synchronous scan is not a resumable cross-request job. Current warm synthetic results do not establish production capacity. No push/deployment or new major phase is authorized by this plan alone.
