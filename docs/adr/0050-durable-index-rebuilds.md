# ADR 0050: Durable index rebuild ownership and uncertain outcomes

[简体中文](0050-durable-index-rebuilds.zh-CN.md)

Status: Accepted

Date: 2026-10-25

## Decision

Migration `20261025_0016` adds one `embedding_jobs` row per project with the latest execution UUID, owner, running/succeeded/failed state, timestamps, result and sanitized error. The existing explicit synchronous rebuild endpoint claims this row under the project lock and commits ownership before provider work. Concurrent running requests return 409. Each embedding batch renews a 900-second lease; a final execution fence and project lock precede vector persistence. Superseded executions cannot finish or overwrite the replacement owner. This remains a synchronous API, not a background queue.

`GET /projects/{id}/embeddings/rebuild-status` is provider-free and restores visible state after refresh. An expired running lease reports `interrupted=true`; retry requires the explicit `retry_interrupted=true` action and never happens automatically. Provider billing cannot be rolled back or guaranteed exactly once after an interrupted request. Successful vector writes retain existing hash reuse and transactional behavior.

The client distinguishes unavailable reads from uncertain write results, including lost/invalid success bodies. It offers status inspection for uncertain rebuild outcomes, preserves running controls during status refresh, and never labels clearing the page as server cancellation. Request budgets are 30s for ordinary/local reads, 240s for vector search and rebuild waiting, 420s for questions, and 240s/900s for single/tool call analysis. Longer rebuilds remain inspectable through persisted status.

## Consequences

Index updates survive browser refresh as observable server operations and duplicate requests are blocked across clients. Existing extraction/parsing leases remain independent; questions and call analysis are still non-persistent and are not newly resumable jobs. A lost server process requires an explicit interrupted-operation retry after lease expiry. No framework, automatic paid retry or formal-knowledge mutation is added.
