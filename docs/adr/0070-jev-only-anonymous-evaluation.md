# ADR 0070: Jev-only anonymous evaluation

[简体中文](0070-jev-only-anonymous-evaluation.zh-CN.md)

- Status: Accepted
- Date: 2026-10-30

## Decision

The user selects Jev model grading without human grading. This supersedes the earlier plan to defer human blind review; it does not remove human review of knowledge candidates. Human grading coverage remains exactly 0%. Model results never populate historical human score fields or imply human agreement. Frozen corpora, gold annotations and old results remain untouched; no holdout-driven prompt/threshold tuning is allowed.

Use `scripts.jev_evaluation prepare` to validate the dataset, require complete answer exports per method, verify exact cited source lines, shuffle anonymous review IDs and separate the method/case mapping in `grading-key.json`. The judge sees neither method names, model identity, original case IDs nor generator confidence. Missing answer exports fail rather than being fabricated. Legacy flat exports are judged at answer granularity, without manufactured claim attribution. New public acceptance exports include claims and their evidence mapping.

Use `scripts.jev_evaluation run` for a provider-free preflight by default. Real evaluation requires an explicit `--allow-jev-calls`, configured key and sufficient `--max-requests` for all planned work. Each attempt is reserved in the exclusive new output directory before transport; failed/unknown calls count. No retries, resume, overwrite or automatic model calls from UI/API/Worker are added. Jev usage is separate from the existing DeepSeek/embedding ledger. This turn explicitly authorizes local verification only, with zero real Jev requests.

Pin `TYPESAFE_MODEL=jev-1.14.0`; aliases are rejected and returned model identity must match. Configure `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL` and `TYPESAFE_TIMEOUT_SECONDS` in backend/.env. The live key stays empty until the user supplies it; .env.example contains placeholders only. HTTP input is capped at 24000 UTF-8 JSON bytes and output at128 KiB; these are guards, not tokenizer estimates. No SDK dependency or implicit retry is introduced.

Separate correctness, required-fact coverage and abstention questions (reference facts provided) from citation support (only one claim and its exact cited passages with up to three surrounding source lines). Supported claims are checked with both option orders; disagreements or confidence below0.8 are flagged uncertain, never automatically treated as human-confirmed truth. This fixed threshold is a review flag, not a calibrated accuracy guarantee. Jev generates typed choices/probabilities, not explanatory prose. The resulting report records protocol, packet hash, model, reservations, typed decisions and human coverage0; it is not a proof of semantic correctness.

## Sources and verification

The transport follows the official [System One API](https://docs.typesafe.ai/api/system-one), [model IDs](https://docs.typesafe.ai/models), [Choice](https://docs.typesafe.ai/primitives/choice) and [citation cookbook](https://docs.typesafe.ai/cookbooks/citation_check). Known [limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13) motivate explicit scope and order checks; they do not establish performance of another version on this project.

Tests use local HTTP substitutes and temporary packets to cover strict transport, bounds, sanitized errors, missing/changed outputs, exact quotes, anonymization, separated reference/evidence inputs, pre-call reservations and zero-call preflight. A real frozen public-v2 BM25 export was prepared locally:20 reviews,54 planned requests,0 reserved/completed,0 model grades,0 human grades. No quality scores are claimed. Live evaluation remains unrun at the user's explicit request.
