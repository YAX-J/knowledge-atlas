# ADR 0041: Run bounded multi-language cross-file call analysis through an Agent

[简体中文](0041-bounded-multilanguage-agent-call-analysis.zh-CN.md)

- Status: Accepted
- Date: 2026-10-24

## Context

Java already has conservative repository-local call hints, while the Tree-sitter languages only expose syntax outlines. Reimplementing a complete symbol solver for every language is outside this project's scope, but sending an entire repository to a model would be expensive, unverifiable, and vulnerable to source-code prompt injection.

## Decision

- Add explicit synchronous `POST /sources/{source_id}/agent-call-analysis`. Opening a source never invokes a model.
- Extract call sites and declarations locally. Build candidates only from ready sources in the same repository boundary and compatible language family: Java; Python; JavaScript/JSX/TypeScript/TSX; Go; C/C++; or C#.
- Scan at most 99 related sources and 20 MiB, analyze at most 100 candidate-bearing calls, and expose at most 20 declaration candidates per call. The request also obeys the configured extraction input-character limit.
- Give the Agent only stable call/candidate IDs, paths, numbered source context, and exact declaration lines. Source content is untrusted data, not instructions.
- Require one structured decision for every supplied call. The Agent may select only server-provided target IDs and must return `resolved`, `ambiguous`, or `unresolved`, confidence, and a short displayable basis. The backend rejects incomplete, duplicate, structurally inconsistent, or out-of-candidate output.
- Return exact call/declaration evidence from server-owned source text. Results are ephemeral derived hints: they are not persisted, promoted, or written to the formal graph.
- If no repository-local candidate exists, return an empty result without a provider call. The desktop UI labels the explicit cost boundary and keeps loading, empty, error, retry, syntax-error, and truncation states visible.

## Consequences

The same safe workflow now covers every supported code language without claiming compiler completeness. Java retains deterministic analysis and lets the Agent disambiguate its bounded candidates. C/C++ results remain especially dependent on missing include paths, macros, and `compile_commands.json`; all languages may miss generated code, external dependencies, dynamic dispatch, reflection, dependency injection, aliases, or data-flow-dependent receivers.

This is one bounded structured Agent step, not a persistent multi-turn planning Agent. Real-provider quality, latency, cost, and prompt-injection acceptance remain separate from simulated tests and should be measured with the frozen evaluation workflow before expanding budgets.

## Verification

Agent-executed on 2026-10-24: 159 focused parsing/call-analysis tests and the complete backend suite (552 passed, 4 explicit native/network skips) passed with one existing Starlette deprecation warning. The frontend production build passed. A 1440×1100 desktop Chrome walkthrough with an isolated mock API covered explicit invocation, loading locks, a validated result, a zero-candidate/no-provider result, a 503 error, keyboard retry, long paths, panel scrolling, and horizontal overflow; no application console error appeared. No real model, GitHub, business database, or provider cost was involved.
