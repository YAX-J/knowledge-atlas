# Cloudflare Workers AI anonymous evaluation

[简体中文](CLOUDFLARE_EVALUATION.zh-CN.md)

Offline grading supports Workers AI as an alternative to [Jev](JEV_EVALUATION.md). Human grading coverage stays 0%; formal graph promotion still requires human review. Local HTTP-substitute verification does not establish live compatibility, quality, latency or billing. No real provider calls were made during implementation.

## Configure locally

`backend/.env` and `.env.example` contain these placeholders. Supply your account ID and Workers AI API token locally; never commit the token or send it in chat.

```dotenv
EVALUATION_PROVIDER=cloudflare
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_MODEL=@cf/cloudflare/clef-flash
CLOUDFLARE_JUDGE_MODE=decision
CLOUDFLARE_TIMEOUT_SECONDS=60
CLOUDFLARE_MAX_TOKENS=2048
```

Account IDs are 32 hexadecimal characters; follow the [official token setup](https://developers.cloudflare.com/workers-ai/get-started/rest-api/). Existing Jev fields remain available. Settings without `EVALUATION_PROVIDER` retain the legacy `jev` default; new environment examples select Cloudflare. No SDK/dependency changes are required.

## Request formats

Both modes use `POST https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}` with Bearer authentication and unwrap `success/result/errors`. There is no automatic model discovery, format fallback or provider fallback.

| Mode | Configuration and request | Output |
| --- | --- | --- |
| `decision` | `@cf/cloudflare/clef` or `@cf/cloudflare/clef-flash`; sends short `model=clef` / `clef-flash`, `state`, `questions` | Validated model identity, Choice labels, finite probabilities and confidence |
| `chat` | Text model supporting `messages` and JSON Schema `response_format` | Validated Choice labels only; confidence and probabilities stay null |

For a text model, change both fields, for example:

```dotenv
CLOUDFLARE_MODEL=@cf/qwen/qwen3-30b-a3b-fp8
CLOUDFLARE_JUDGE_MODE=chat
```

This adapter does not support every catalog task: embeddings, reranking, speech, image generation and text models without the required structured-output capabilities are outside this interface. Unsupported requests fail without retry. Check each model's current availability/capabilities. Sources: [Clef](https://developers.cloudflare.com/workers-ai/models/clef/), [Qwen](https://developers.cloudflare.com/workers-ai/models/qwen3-30b-a3b-fp8/), [JSON Mode](https://developers.cloudflare.com/workers-ai/features/json-mode/).

## Zero-call preparation and preflight

Run from `backend`; every output directory must be new:

```powershell
.\.venv\Scripts\python.exe -m scripts.judge_evaluation prepare --dataset ../evaluation/public-v2 --predictions ../evaluation/results/2026-10-26-public-v2-run1/bm25.jsonl --output ../output/cf-my-run/packet
.\.venv\Scripts\python.exe -m scripts.judge_evaluation run --provider cloudflare --packet ../output/cf-my-run/packet --output ../output/cf-my-run/preflight
```

Preflight needs no token/account and makes no HTTP calls. It validates packet integrity, configuration and the final wire payload's 24000-byte UTF-8 JSON limit. Inspect `planned_requests`, `requested_model`, `judge_config` and `judge_config_sha256` in `run.json`; reservations/completions/grades remain zero. The historical 20-answer example plans 54 requests. Changing model/mode requires a new preflight/report. Fix the judge/protocol before holdout use; never select judges using holdout outcomes.

Packets are provider-neutral and retain the legacy `jev-anonymous-claims-v1` format identifier. Original `scripts.jev_evaluation` imports/commands remain supported; use `--provider jev` for Jev runs when the environment selects Cloudflare.

## Separately authorized live run

Future use only, after configuring credentials and explicitly authorizing provider and count. Replace 54 with another packet's actual planned count:

```powershell
.\.venv\Scripts\python.exe -m scripts.judge_evaluation run --provider cloudflare --packet ../output/cf-my-run/packet --output ../output/cf-my-run/live --allow-judge-calls --max-requests 54
```

`--allow-jev-calls` cannot authorize Cloudflare. Attempts are reserved on disk before HTTP; failed/unknown outcomes count and stop the run without automatic retry/resume. Existing output directories cannot be overwritten. Each new live run requires separate authorization; it does not reset the historical84-model/61-embedding ledger. API/Worker/page reads never invoke grading. Business DeepSeek generation and embedding integrations are unchanged.

## Interpretation and limits

Anonymization, exact source-quote checks, reference-based correctness/completeness/abstention and citation-only support stay unchanged. Every cited unit is checked in both option orders. Reports record provider/model/mode/protocol/configuration hash, decisions and actual usage when available; absent CF usage stays null. CF catalog IDs are not verified immutable weight revisions (`model_revision_pinned=false`); absent returned model identity stays null in chat mode.

Chat labels have `confidence=null` and `probabilities=null`; generated confidence is never treated as calibrated probability. These citation units are conservatively included in `uncertain_units`, even when both choices agree. Decision-mode order disagreement or confidence below0.8 also flags uncertainty; the threshold is not calibrated on this project. These are model judgments, not human accuracy or proof of entailment; human-score fields remain empty.

Responses are streamed with a128 KiB cap, finite timeout, no redirects/retries. Duplicate keys, markdown-wrapped JSON, missing/extra answers, invalid choices, incomplete outputs and malformed usage are rejected. Reports exclude provider bodies, raw prompts, credentials and generated explanations. No database schema, business API, UI or graph-write behavior changes.
