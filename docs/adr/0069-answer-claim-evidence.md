# ADR 0069: Claim-level answer evidence

[简体中文](0069-answer-claim-evidence.zh-CN.md)

- Status: Accepted
- Date: 2026-10-30
- Supersedes the flat output portion of ADR 0011; citation ownership and retrieval scope remain.

## Context

A valid flat citation list does not show which conclusion uses which passage. One paragraph can mix supported facts and unsupported details. Existing conversations and workflow checkpoints already persist flat answers, and frozen experiments must keep their original interpretation.

## Decision

Use versioned `evidence-claims-v2` provider output: 1–8 claims, each with text (1–500 characters), status (`supported` or `insufficient`) and unique citation UUIDs. Supported claims require citations; insufficient claims cannot cite and must describe what cannot be confirmed. Reusing a citation across claims is allowed; at most five distinct citations and 4000 joined characters are allowed per answer. Overall support is true exactly when every claim is supported; otherwise missing information is required. Partial support retains the cited claims.

The model emits no independent flat prose or top-level citation list. The server joins claim texts using double newlines and derives the first-occurrence union of citations. Existing `answer`, `evidence` and primary `entity_ids` attribution remain available. Every citation must belong to the current user/project/time-scoped retrieval pool, including read-only tool additions. Unknown citations fail with `QUESTION_EVIDENCE_INVALID`; malformed single-step/tool output fails with `QUESTION_OUTPUT_INVALID`/`CALL_AGENT_OUTPUT_INVALID`, without automatic retry. Empty retrieval produces one insufficient claim without a provider call.

Both live provider and tool-loop parsing require `ClaimAnswerDraft`; the old `AnswerDraft` remains only for legacy diagnostic adapters/fixtures. New experiment manifests record the answer protocol; frozen data/results and candidate-extraction prompt identity remain unchanged. No paid experiment is part of this change.

`QuestionRead` adds nullable `claims` and `answer_protocol`, so old stored conversation/workflow answers remain readable without migration, inferred per-claim attribution or provider replay. New answers persist these fields through existing JSON checkpoints. Frontend `AnswerClaims` is shared by question/conversation and collaboration views. Each citation opens its exact source/chunk through existing evidence navigation; unavailable IDs cannot open a guessed source. Legacy answers retain flat prose with a notice. All content uses text interpolation.

## Consequences

The schema detects omitted citations, unsupported status combinations and out-of-pool IDs. It cannot prove that a cited passage entails the claim, that the model split every factual assertion correctly, or that it did not mislabel an assertion as insufficient. The UI says “附有引用” and asks users to inspect the source. Human blind grading remains deferred to the user. No additional model verification pass or new paid request is introduced. Schema head stays `20261029_0019`; the cumulative paid ledger remains 84 model /61 embedding attempts.

## Verification

The user's existing choice of Agent execution carries forward. Focused backend tests cover strict schema/provider parsing, partial support, foreign-project evidence rejection, persisted legacy read/replay, tool-output omissions without retries, conversations and evaluation compatibility. Frontend tests cover claim order versus evidence order, exact navigation, insufficient claims, safe text, unavailable IDs, old records and collaboration read-only restoration. Full backend coverage, native owned-schema acceptance, frontend coverage/build and a desktop Chrome local-substitute walkthrough are required; their results are recorded below after execution. Native fixtures do not establish model quality.

Actual results: backend **773 passed /8 skipped**, statement coverage **95.57%** with `KA_NATIVE_COMPILERS=1`; native PostgreSQL17.10/pgvector0.8.7 **195 passed**, migration upgrade/downgrade/upgrade passed, disposable schema removed and application migration marker unchanged. Frontend **132 passed /18 files**, configured statement coverage69.73% and line coverage74.42%; strict type checks and production build passed. Desktop Chrome1440×900 used the real API with owned temporary schema and local provider substitutes: no-evidence refusal, mixed support, exact line6–8 chunk focus, persisted conversation reload, tool-workflow saved claims, legacy-format notice, keyboard-visible citation focus, scrolling and no horizontal overflow passed. Browser reported no runtime errors; the named browser, recorded services and QA schema were closed/removed. Screenshots remain ignored in output/answer-claims-20261030. No real provider calls, external sync or human grades were produced.
