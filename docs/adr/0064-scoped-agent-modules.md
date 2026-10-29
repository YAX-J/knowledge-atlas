# ADR 0064 Scoped agents inside the existing application

[简体中文](0064-scoped-agent-modules.zh-CN.md)

- Status: Accepted
- Date: 2026-10-29

## Decision

Keep one backend/frontend project. Separate `agents`, `workflows`, read-only `tools`, `analysis` and `llm` within `backend/app`. Register code-analysis, knowledge-extraction and evidence-QA roles. Agents receive immutable source snapshots or scoped read callbacks, not database sessions. Application services retain authorization, schema/evidence validation, transactions and human promotion. Existing moved service imports are aliases to canonical modules, preserving old endpoint and monkeypatch behavior. Native compiler helper files remain in the existing scripts directory.

Use a pinned LangGraph dependency for bounded model/tool loops and explicit coordinating workflows. Share user/project/source/snapshot/time/run context and atomic attempted-request counters across roles. Enforce per-role and global request/tool/input/output/time budgets; count failed attempts and never automatically retry paid calls. Disable tracing upload for graph invocation. Events contain fixed vocabulary/numeric metadata; raw prompts and tool arguments are not persisted as events. Source text/tool output is untrusted data. Derived code findings are hints, never formal evidence or direct graph writes.

## Consequences

This gives new agents one registration and workflow extension path without duplicating provider clients or applications. Existing parsing Worker and single-step APIs remain compatible. Dependency weight increases; bounded serial flows do not imply arbitrary planning, production authentication or complete build/runtime semantics. Human review remains the sole formal graph-write boundary. See [implementation](../MULTI_AGENT.md).
