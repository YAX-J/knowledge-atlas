# Knowledge Atlas implementation plan

[简体中文](PLANS.zh-CN.md)

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

The user will complete [the existing blind review](evaluation/holdout-v3/README.md). Do not invent grades or represent Agent-authored gold data as human evaluation. Genuine personal technical notes were not supplied; v3 uses genuine public upstream documents and is labeled accordingly. Paid v3 testing requires the existing cumulative budget ledger, separate versioned output and an unchanged test split. No v3 quality score exists yet.

Private repository acceptance, privileged fresh-database recovery, Docker and remote CI need their actual environments. They remain explicit limits, not hidden assumptions about completion.

## Planning rules

Preserve evidence, user/project scope, explicit human graph writes and additive migration safety. Proposed future work should follow measured failures: bounded full-text pagination beyond 1k, representative semantic/vector benchmarks, then index/caching decisions. Current warm synthetic results do not establish production capacity. No push/deployment or new major phase is authorized by this plan alone.
