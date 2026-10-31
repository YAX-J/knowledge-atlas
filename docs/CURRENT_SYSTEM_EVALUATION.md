# Current-system end-to-end question evaluation

[简体中文](CURRENT_SYSTEM_EVALUATION.zh-CN.md)

Latest 2026-10-31 status: the user authorized an independent96/73 round and live holdout-v3 started. The fifth BM25 answer failed with `QUESTION_OUTPUT_INVALID`;4 answers are saved and round usage is5/1. No retry, judge requests0, human coverage0%. See the [live run record](../evaluation/results/2026-10-31-holdout-v3-run1/REPORT.md). The original protocol and pre-authorization budget checkpoint below remain; partial output is not completed quality acceptance.

The recorded local zero-call configuration, fingerprints and budget blocker are in [preflight.json](../evaluation/experiments/2026-10-31-current-system-v3/preflight.json). This record consumes no authorization and is not a budget approval.

`--authorization-ledger` uses only an existing explicitly approved96/73 holdout grant, bound to dataset/model scope. It locks and atomically persists before requests, claims one output on execution, preserves the historical84/61 ledger and never creates authorization on use. Unused91/72 cannot automatically retry/resume/replay in a new output. Subsequent failure-observability changes record exception classes, validation-error type counts and the current case, without inputs, model text or error messages; they cannot retroactively recover this failure's missing details.

## Fixed protocol

| Item | Rule |
| --- | --- |
| Development/test | v1/public-v2 for development; holdout-v3 for independent testing, never ranking/prompt/judge/threshold tuning |
| Data | Existing 7 pinned public documents, 24 cases: 8 direct, 8 cross-document, 4 temporal, 4 unanswerable; bytes and reference annotations unchanged |
| Methods | BM25, Vector, Hybrid, RRF, 24 cases each; same curated reviewed graph, index, answer model and configuration |
| Online path | `questions.answer_question`, `single_step`, 5 entities, at most 12 answer input passages, `evidence-claims-v2` |
| Time | Pass each `case.valid_at`; never force historical cases to current time; check vector coverage in that scope |
| Primary metric | Existing `line-evidence-v2` macro evidence Recall@5; K counts exported evidence records, not entities |
| Additional metrics | Citation F1, raw model correctness/completeness/abstention labels, low-confidence rates, per-claim double-order support/uncertainty, latency and attempted/reported usage |
| Categories | Report direct/cross-document/temporal/unanswerable separately; cited supported claims are the citation-support denominator; uncited/insufficient items are separate |
| Interpretation | Preserve paired per-case results and difference intervals; small related cases and single-run network latency do not establish general superiority or capacity |
| Retained limits | Search returns at most 3 evidence records per entity; structural checks do not establish entailment; curated review replay does not measure automatic extraction quality |
| Judge | Proposed existing CF `@cf/cloudflare/clef` decision protocol and 0.8 uncertainty threshold; never select judges on holdout scores; disclose unpinned weights. Review preflight configuration and authorize separately before live use |

Formal knowledge still requires human review. Model labels never populate human `answer_correct` / `explainability_score`. Preserve historical exports without inferred claim attribution.

## Entry changes

`scripts.run_public_acceptance` accepts public-v2 and holdout-v3; the latter skips the two public-v2-only code extraction smoke cases. `--preflight` requires no credentials, DB or provider access. It validates frozen data/fixtures, estimates calls and reads the historical ledger without changing it.

Preflight records answer/embedding models, dimensions, batch size, dataset/fixture/protocol and application code fingerprints. Live holdout use also requires `--approved-plan <run.json>` to match the recomputed plan exactly. Changed inputs, code, models or ledgers require a fresh preflight. A preflight file does not authorize calls.

The `online-claims-export-v1` format preserves per-case time, claims, claim citations, actual answer input pool and retrieval metadata. The frozen numeric scorer receives a compatible `<mode>.metrics-input.jsonl` projection; rich `<mode>.jsonl` exports feed anonymous judging. The frozen prediction schema is unchanged. Partial outputs, before-call reservations, fail-stop behavior and no retries/resume/overwrite remain.

## Zero-call preparation and budgets

From `backend`, use a fresh output directory:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_public_acceptance --dataset ../evaluation/holdout-v3 --output-dir ../output/holdout-v3-new/preflight --model-limit 96 --embedding-limit 73 --preflight
```

At batch size 32 with 19 fixture entities:

| Kind | Round upper bound | Historical reserved / original limit | Remaining |
| --- | ---: | ---: | ---: |
| Answer model | 96 (24×4; local no-evidence refusal can reduce this) | 84 / 120 | 36 |
| Embedding | 73 (1 index batch + 24×3 queries) | 61 / 160 | 99 |
| Judge | Exact count after actual supported-claim exports | Prior Clef 214 calls are a separate historical record | Never inferred from prior authorization |

Current preflight reports `status=prepared`, zero reservations/completions and the answer-budget blocker. Live use fails before DB/provider access. Fresh directories never reset historical usage. A complete four-method round requires explicit new answer authorization, preserving the old ledger and recording the new grant before repeating preflight. Live embedding use also requires explicit round authorization despite remaining cumulative capacity. Judge calls are `1 + 2*cited supported claims` per answer: at most 1632 for 96 answers. This structural ceiling is not an exact plan; determine the actual count after export and authorize it separately.

Future command shape, **rejected under current authorization**; do not execute before reconciling budgets and obtaining a fresh reviewed plan:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_public_acceptance --dataset ../evaluation/holdout-v3 --output-dir ../output/holdout-v3-new/live --approved-plan ../output/holdout-v3-new/preflight/run.json --model-limit 96 --embedding-limit 73 --allow-model-calls --allow-embedding-calls
```

## Thesis and demonstration outputs

Generate method/category tables, failure cases and figures only after the live run; no current-system scores are fabricated now. Separate retrieval metrics, automated model grades, human coverage 0%, public-document provenance, simulated history and curated review fixtures. Prepare four saved demonstration cases: direct fact, cross-document evidence, historical scope and no-evidence refusal. Avoid repeated paid calls during defense. Holdout discoveries require separate future development data.

## Preparation checks before live authorization

The user selected Agent-run offline checks. Focused coverage includes fingerprints/mappings/exact citations, unchanged inputs, 96 current-QA exports through SQLite/local provider substitutes, historical time, before-call ledger reservations, fail-stop behavior, budgets and approved-plan gates. Substitute results are engineering checks, never holdout quality scores. Focused combination: **115 passed**; full backend: **931 passed / 11 skipped**; final preflight metadata checks: **19 passed**. `git diff --check`, bilingual links and historical input SHA-256 checks pass; the original ledger remains84/61.

Initial sandbox checks stopped because of pytest temporary-directory access and TestClient stalling. Passing runs used the same venv, explicit fresh `--basetemp` directories under project `output`, and authorized execution outside the sandbox. Full command from `backend`: `.\.venv\Scripts\python.exe -m pytest --basetemp=../output/pytest-evaluation-full-20261031 --tb=short`. No UI/schema changes require frontend build/browser checks; no full native PostgreSQL live experiment was run this turn.
