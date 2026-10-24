# ADR 0043: Bounded read-only repository tools

[简体中文](0043-bounded-read-only-tool-agent.zh-CN.md)

- Status: Accepted
- Date: 2026-10-24
- Extends: ADR 0041; no storage migration

## Decision

Keep `single_step` as the compatible default. Explicit `strategy=tools` runs a plain-Python, synchronous DeepSeek function-calling loop; LangGraph is not a dependency. Tool choice is required on the first turn, auto on middle turns and none on the final permitted turn. The protocol follows the provider's [tool calling guide](https://api-docs.deepseek.com/guides/tool_calls/), with thinking disabled. No internal reasoning is returned or logged.

Expose only `read_source_range`, `get_imports`, `search_symbols`, `find_references`, `get_type_members` over already authorized immutable source snapshots and existing declaration candidates. No filesystem paths, SQL, shell, network, graph mutation or provider tools are exposed. Unknown names, extra arguments and out-of-scope IDs are rejected. Source text and tool results are untrusted data, never authority.

Budgets: four provider turns, eight tools, 230 seconds, 20000 cumulative tool-output characters, 240000 cumulative serialized input characters. Individual reads are at most 80 lines. An over-budget or invalid final result fails explicitly. The same strict final decision/target-ID and exact evidence validation applies to both modes. Results and sanitized execution traces remain non-persistent, outside the parsing Worker and formal graph.

## Consequences

The frontend exposes the choice, locks context while running, and shows tool name/status/duration without private reasoning. Gold cases are separately versioned: 30 public synthetic snippets, 50 line-exact cases, ten language variants. All modes share the candidate generator; tools cannot create absent candidates. This is bounded evidence investigation, not a general planning or coding Agent. Candidate coverage, exact decision accuracy, precision/recall and latency are reported separately.

The actual approved acceptance is preserved under `evaluation/results/2026-10-24-models`. Frozen answer replay is separate from online retrieval. Numeric usage is recorded; missing billing amounts and human grades remain null. Human labels require real reviewer input. Scientific figures are generated from frozen metrics with input hashes; no result is silently tuned away.
