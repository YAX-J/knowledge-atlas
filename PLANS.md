# Knowledge Atlas implementation plan

Current evaluation policy: anonymous model grading explicitly selects Jev or Cloudflare Workers AI; human coverage0%, no live calls this turn. CF decision/chat adapters and zero-call preflight are implemented; live compatibility/quality remain unverified. See [CF setup](docs/CLOUDFLARE_EVALUATION.md) and [ADR0072](docs/adr/0072-cloudflare-judge-adapter.md). Ordered read optimizations remain in ADR0071.

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

The user selects Jev-only anonymous grading with human coverage0%. Real Jev evaluation is deliberately unrun this turn; the adapter and provider-free packet/preflight are available. Keep v3 frozen and separate from development data; never tune judge prompts, ranking or thresholds against it. Historical human-score fields remain untouched.

Private repository acceptance, privileged fresh-database recovery, Docker and remote CI need their actual environments. They remain explicit limits, not hidden assumptions about completion.

## Planning rules

ADR 0068 completes explicit collaboration-page retrieval/time/code selection, context-fenced read-only metadata loading, draft previews and saved scope projection. Preserve the BM25 default and same-UUID replay behavior; historical questions exclude current code. Focused/full/native/frontend/browser acceptance is recorded in that ADR; genuine answer-quality evaluation remains separate.

The next reliability slice (ADR 0067) persists per-event call reservations and validated step checkpoints, fences/renews active executions and keeps partials on failure. The user retained Agent verification; focused/full/native/frontend/browser results are recorded in the ADR. Execution remains synchronous and interrupted tasks are read-only on replay; automatic node continuation is outside this change.

The 2026-10-30 lexical coverage change replaces the 1k window with 200-entity keyset batches and a 50k explicit scan budget, shared global BM25 statistics, bounded per-entity evidence and v2 protocol metadata (ADR 0066). Regression/acceptance results are recorded in that ADR after execution; historical experiments and the holdout remain unchanged.

Preserve evidence, user/project scope, explicit human graph writes and additive migration safety. Future work should measure the v2 batch scan and representative semantic/vector workloads before index/caching decisions. The synchronous scan is not a resumable cross-request job. Current warm synthetic results do not establish production capacity. No push/deployment or new major phase is authorized by this plan alone.
