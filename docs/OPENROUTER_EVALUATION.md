# OpenRouter Jev anonymous evaluation

[简体中文](OPENROUTER_EVALUATION.zh-CN.md)

The offline judge runner supports `openrouter`, alongside direct TypeSafe `jev` and native `cloudflare` adapters. This route keeps Jev as the judge. Human grading coverage remains0%; formal graph promotion still requires human review. Development used HTTP substitutes and zero-call preflight only, not live account, payment or model-quality verification.

## Configuration

Fill the key locally in `backend/.env`; do not send or commit it. The real local environment and `.env.example` contain:

```dotenv
EVALUATION_PROVIDER=openrouter
OPENROUTER_API_KEY=
OPENROUTER_MODEL=typesafe/jev-1.14
OPENROUTER_TIMEOUT_SECONDS=60
```

Create a key in [OpenRouter settings](https://openrouter.ai/settings/keys). Account credit/payment/region availability must be checked in your own account; integration does not establish eligibility. The local provider selection changes to OpenRouter; existing CF/TypeSafe credentials are preserved. Settings without a provider field retain the legacy `jev` default. No SDK or dependency is added.

## API and model identity

The adapter sends Bearer-authenticated `POST https://openrouter.ai/api/alpha/decisions` with `model`, `state`, `questions` and `provider.allow_fallbacks=false`. It does not use chat completions, the CF `input` envelope or `/v1/systemone`. Only the Choice judgments required by this evaluation are supported; this is not a general adapter for all OpenRouter models or business QA/extraction/embeddings.

Use the OpenRouter model ID `typesafe/jev-1.14`, not the CF/direct `jev-1.14.0` spelling. Explicit `typesafe/jev-<major>.<minor>` releases and dated snapshot IDs are accepted; `latest` aliases and unversioned IDs fail before HTTP. A release can return a dated ID such as the vendor's documented `typesafe/jev-1.13-20260917`; retain the actual returned identity. The adapter accepts only the requested release and an optional valid eight-digit date suffix. An explicitly selected snapshot must match exactly.

A release selector is not an immutable snapshot (`model_revision_pinned=false`). `run.json` records `requested_model`, each actual response model, the judge configuration/hash and `resolved_model`. If the actual model changes within a run, preserve both results and attempts, mark the run failed and stop before another request. Do not select judges or tune prompts/thresholds using holdout-v3. Freeze the evaluation protocol first. See the official [Jev guide](https://openrouter.ai/docs/guides/community/jev), [response example](https://openrouter.ai/docs/guides/community/jev-tutorial) and [Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request).

## Provider-free preparation and preflight

From `backend`, use a new directory for every output:

```powershell
.\.venv\Scripts\python.exe -m scripts.judge_evaluation prepare --dataset ../evaluation/public-v2 --predictions ../evaluation/results/2026-10-26-public-v2-run1/bm25.jsonl --output ../output/or-my-run/packet
.\.venv\Scripts\python.exe -m scripts.judge_evaluation run --provider openrouter --packet ../output/or-my-run/packet --output ../output/or-my-run/preflight
```

Preflight needs no API key and makes no HTTP requests. It validates packet integrity, model selection and the full24000-byte UTF-8 JSON request limit. Inspect the planned count and configuration in `run.json`; reservations/completions/model grades remain0. The historical20-answer BM25 example plans54 requests. Old flat answers keep answer-level granularity; new claim exports preserve per-claim attribution. The existing provider-neutral packet and legacy `scripts.jev_evaluation` entry point remain supported.

## Future separately authorized live run

The following is documentation only; this development turn has no live requests. After configuring the key and explicitly authorizing the selected provider and count:

```powershell
.\.venv\Scripts\python.exe -m scripts.judge_evaluation run --provider openrouter --packet ../output/or-my-run/packet --output ../output/or-my-run/live --allow-judge-calls --max-requests 54
```

Use another packet's actual planned count. `--allow-jev-calls` authorizes only direct TypeSafe, not OpenRouter. Every attempt is reserved on disk before HTTP; failures/timeouts/unknown outcomes count. Errors stop without automatic retry/resume, and existing output directories cannot be overwritten. New result directories do not erase earlier usage or grant new budgets. OpenRouter authorization is separate from the historical84-model/61-embedding ledger and CF smoke attempts; neither is reset or reused. API/Worker/page reads never invoke grading.

## Output, networking and limits

Keep anonymized inputs, exact source checks, reference-based correctness/completeness/abstention and citation-only support. Validate every answer key/Choice, finite probabilities and confidence; retain both option orders and flag disagreement or confidence below0.8. These probabilities/thresholds do not establish project-calibrated accuracy or human agreement; human-score fields stay empty.

Usage requires nonnegative integer input/output counts; optional `usage.cost` is a finite nonnegative provider-reported USD amount, or null if absent. Do not invent missing costs or infer exact invoices. Reject wrong models, malformed/duplicate JSON, missing/extra judgments and invalid usage. Stream responses with a128 KiB cap, finite timeout and no redirects. Default HTTPX transport preserves environment/system proxy discovery and has zero retries; connection/read timeouts have distinct sanitized codes. Authentication, payment and rate-limit failures also have static codes; raw error bodies and credentials are excluded. Neither client nor request enables provider fallback.

This change does not implement the separate CF third-party unified Jev route. Earlier local CF smoke artifacts remain historical records, including400/402/timeouts; they are not successful Jev evaluations. Direct TypeSafe and CF native judging remain explicitly selectable.
