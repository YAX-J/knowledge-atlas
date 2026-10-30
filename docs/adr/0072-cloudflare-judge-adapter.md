# ADR 0072: Explicit Workers AI judge adapters

[简体中文](0072-cloudflare-judge-adapter.zh-CN.md)

- Status: Accepted
- Date: 2026-10-30
- Extends ADR0070's provider choice; anonymous model-only grading and human coverage0% remain.

## Decision

Add an offline provider selector and native Cloudflare REST adapter with explicit decision/chat modes. Clef/Clef-flash use typed state/questions and validated probabilities; compatible text models use messages and JSON Schema labels only. Chat confidence/probabilities stay null and citation units uncertain. No automatic model, format or provider switching.

Keep provider-neutral packets and the legacy Jev CLI/import path; add scripts.judge_evaluation and --allow-judge-calls. The Jev-only flag cannot authorize Cloudflare. Preserve per-attempt disk reservations, full planned-request caps, zero-call preflight, new output directories and fail-stop without retry/resume. Record model/mode/protocol/configuration hash, actual usage or null and the absence of verified pinned CF weight revisions. Credentials never enter reports.

## Consequences

Only text judging is covered; no generic support for all Workers AI tasks, AI Gateway/external catalog providers, business QA/extraction/embedding switching, UI, migrations or graph writes. Responses are bounded to128 KiB and requests to24000 UTF-8 JSON bytes. Official API documentation informed the adapter; HTTP substitutes do not establish live compatibility or quality. Holdout/frozen results and old provider ledger remain unchanged. Configuration alone does not authorize paid calls. See [the guide](../CLOUDFLARE_EVALUATION.md).

## Verification

Focused CF/Jev/evaluation regressions:79 passed. Full backend with KA_NATIVE_COMPILERS=1:862 passed,8 skipped, application statement coverage95.70% (90% gate passed). Real CLI preparation plus CF decision, CF chat and legacy Jev preflights each planned54 requests with0 reservations/completions/grades. All333 checked local Markdown targets exist, language companions updated together and git diff --check passed. Local .env is ignored; frozen inputs/results unchanged. No frontend/UI/SQL/migration changes, so no browser/build/native database rerun required. Live provider calls0.
