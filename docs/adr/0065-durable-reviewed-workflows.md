# ADR 0065 Durable workflows with an explicit human checkpoint

[简体中文](0065-durable-reviewed-workflows.zh-CN.md)

- Status: Accepted
- Date: 2026-10-29

## Decision

Add scoped `agent_runs` in additive migration `20261029_0019`. Persist request fingerprint, bounded result/events/usage, execution UUID and lease. Commit the run claim before providers and fence final updates. Repeating the same request UUID/input returns saved state; changed input conflicts and foreign scope remains 404. Expired executions read as interrupted; never infer approval for a paid replay.

Coordinate optional code analysis before extraction or grounded QA using explicit LangGraph edges. Extraction persists only validated candidates and then waits. Save candidate/task/source IDs, recheck exact source hash and every human disposition on resume, and use the existing audited review service for formal graph transactions. Resume performs no provider or indexing calls. Historical QA forbids current-code hints. Existing successful source/strategy extraction remains idempotent across runs.

Expose start/list/read/resume API and a Vue collaboration page with pending UUID persistence, read-before-resend, scoped late-response guards, saved traces and source/evidence links. Hash URLs restore by GET only. Synchronous events are saved on completion, not streamed; a process crash does not provide node-level durable recovery.

## Consequences

Users can inspect and explicitly finish coordinated work while preserving the existing evidence/audit boundary. Migration must be backed up and tested in an owned temporary schema before upgrading the application. A failed/interrupted run requires a deliberate new request; no background queue or automatic paid retry is added. Genuine human grading and provider-quality experiments remain separate acceptance work.
