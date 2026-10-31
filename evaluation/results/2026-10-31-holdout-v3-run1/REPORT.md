# First live holdout-v3 run: stopped with partial results

[简体中文](REPORT.zh-CN.md)

On 2026-10-31 the user authorized up to **96 DeepSeek answer requests and 73 current embedding-service requests**, excluding judging. A separate round ledger preserves the historical84/61 ledger. The seven documents,24 cases, references, ranking, answer prompts and thresholds remain unchanged.

| Item | Observed record |
| --- | --- |
| Status | failed; partial output, not a completed four-method experiment |
| BM25 | 4 saved answers: holdout-v3-01 through holdout-v3-04 |
| Failure position | Fifth answer, holdout-v3-05 by frozen ordering; inferred from request count and saved prefix |
| Error | `QUESTION_OUTPUT_INVALID`: output failed application output/completion/Schema checks |
| Vector / Hybrid / RRF | None started |
| Round reserved / unused | Answers5/96,91 unused; embeddings1/73,72 unused; failed requests count |
| Historical / combined | Historical ledger remains84 model/61 embedding; combined business attempts89/62, kept separately |
| Judging / human grades | New judge requests0; human grading coverage0% |
| Reported answer usage | All5 reported usage:6334 input and857 output tokens; excludes embedding usage; actual billed cost unknown |

The failed raw response was not retained. The error does not identify a particular field or parse failure, so it cannot establish a citation-UUID, claim-length, status-field or network cause. No QA Schema/prompt was changed to accommodate a test case; no failed request was retried. Four answers are not a complete test set: no method comparison, accuracy or quality figures are reported. They have no model or human grades. References are Agent-authored; curated review replay is not extraction-quality evidence or real personal-note history.

## Cleanup and artifacts

Original `run.json` retains `schema_removed=false`: the previous runner sets it only after full success. A separate read-only check in [cleanup-verification.json](cleanup-verification.json) confirms zero temporary `ka_functional_*` schemas, zero experimental-project rows in public, and public migration head `20261029_0019`. The raw run was not rewritten to hide this discrepancy.

- [bm25.partial.jsonl](bm25.partial.jsonl): four answers, claim citations, actual input evidence and retrieval metadata; human fields null.
- [run.json](run.json), [preparation.json](preparation.json): original run and isolated preparation.
- [authorization.json](authorization.json), [authorization-receipt.json](authorization-receipt.json), [preflight.json](preflight.json): user grant, before-call reservations, historical ledger SHA-256 and frozen plan.
- [summary.json](summary.json), [artifact-sha256.json](artifact-sha256.json): partial summary and machine-artifact hashes.
- [executed-code.json](executed-code.json): exact base64-encoded implementation patch and SHA-256 at run start against `02a76bb`, before subsequent observability additions.

Executed from `backend` (record only; the claimed grant/output must not be replayed):

```powershell
.\.venv\Scripts\python.exe -m scripts.run_public_acceptance --dataset ../evaluation/holdout-v3 --output-dir ../output/holdout-v3-live-20261031-r1/live --approved-plan ../output/holdout-v3-live-20261031-r1/preflight.json --authorization-ledger ../output/holdout-v3-live-20261031-r1/authorization.json --model-limit 96 --embedding-limit 73 --allow-model-calls --allow-embedding-calls
```

After failure, sanitized classification was added: future runs record the current case, exception types and Pydantic validation-error type counts without inputs, error messages or model text. It cannot recover this attempt's missing details. Any new diagnostic/repeat attempt still needs explicit authorization. Unused91/72 capacity does not authorize automatic retry. Never tune ranking, prompts, thresholds or references against this failure. No incomplete judge packet was prepared and no judge requests were issued.

## Verification

Scoped-ledger tests: **33 passed**. Full backend: **941 passed / 11 skipped**. Coverage includes missing/changed grants, exhaustion, lock conflicts, inconsistent counters, repeated claims, unchanged historical ledgers and successful/failed complete local-provider substitute flows. The final sanitized-observability addition has a separate focused check: **34 passed**. Passing these checks does not guarantee valid live output. Native preparation/cleanup succeeded; live QA stopped at the error above.
