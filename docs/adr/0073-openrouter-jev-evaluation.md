# ADR 0073: OpenRouter Jev evaluation

[简体中文](0073-openrouter-jev-evaluation.zh-CN.md)

- Status: Accepted
- Date: 2026-10-30
- Extends ADR0070/0072 with a third offline judge provider.

## Decision

Add explicit OpenRouter Jev Decisions API selection, separate local credentials and a versioned release/snapshot model field. Reuse existing httpx, Choice validation, neutral anonymous packets and per-attempt disk reservations. Use the fixed official Decisions endpoint, disable provider fallback, honor environment proxies and retain zero transport retries. Legacy provider flags cannot authorize another provider.

Accept the requested release or its dated snapshot; an explicitly selected snapshot must match exactly. Record requested/actual models, returned token counts and optional reported cost. Stop a run on model drift, preserving every attempted/completed result. Release selectors are not marked immutable. Static sanitized errors distinguish authentication/payment/rate limits and timeout phases. Preserve size bounds and reject invalid JSON/choices/usage.

## Consequences

No business provider, API, UI, schema, graph-write or human-score changes. Human grading remains0%. Native CF support remains unchanged; this does not implement its third-party Jev route. Frozen results/holdout and old ledgers are untouched; all new live runs require explicit authorization. HTTP substitutes do not establish account eligibility or judge quality. See [setup and commands](../OPENROUTER_EVALUATION.md).

## Verification

Focused OpenRouter/CF/Jev/evaluation regressions:132 passed. Full backend with KA_NATIVE_COMPILERS=1:915 passed,8 skipped, application statement coverage95.75% (90% gate passed). Actual CLI preparation and OpenRouter/direct-Jev/native-CF preflights each planned54 requests with0 reservations/completions/model grades and human0. All343 local Markdown targets exist; language companions are synchronized, git diff --check and staged review passed. Local .env remains ignored, frozen inputs/results/old ledgers excluded. No frontend/UI/SQL/schema changes, so no browser/build/native DB rerun. Live calls0; account, payment and model quality remain unverified.
