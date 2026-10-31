# ADR 0077: Explicit durable assistant execution

[简体中文](0077-durable-assistant-execution.zh-CN.md)

- Status: Accepted; locally verified
- Date: 2026-10-31

## Decision

Implement M2 only. `assistant-task-v2` submissions return202 and persist queued tasks without calling providers; v1 remains synchronous200 and legacy AgentRun is unchanged. A separate `python -m app.assistant_runner` claims only async_v2 queued records under scoped row locks / skip locked, issues a new execution token and300-second lease, and runs the same bounded coordinator. Parsing workers never consume these tasks. GET and event/artifact reads never execute, recover or reserve anything.

Migration0021 adds execution mode, revision and measured elapsed milliseconds to tasks, plus assistant_attempts, assistant_steps, assistant_artifacts and assistant_continuations. It preserves prior task/results and defaults existing rows to sync_v1. Downgrade removes new execution history, retains task results and closes unsupported queued/cancelled states as interrupted; it is maintenance, never business undo. Business migration requires verified backup/recovery and preserved old-table content.

Reserve each model/tool attempt before callback, atomically with fenced task usage/events. Commit validated loop state, gateway reference pool and the completed attempt together after each model decision or individual tool result. These are scoped business checkpoints, not operational logs. Events remain content-free. Explicit continuation resumes after the last saved node or tool, without repeating completed transport/tool receipts. A final report and typed artifact commit together under the ownership fence. State is bounded to200000 JSON characters /16 checkpoints, retaining M1 source/output/input/reference/role budgets. Knowledge time is frozen at submission; selected source UUID/hash and snapshot membership are rechecked before execution. No retry/fallback or tracing upload.

Expired executions are interrupted, never requeued automatically. Unsettled attempts become unknown; a transport can complete remotely without a saved receipt. Cancel clears ownership and stops future callbacks/publication, while in-flight usage stays counted. A late worker cannot persist its result. Explicit continue binds a unique control UUID, exact task revision/checkpoint and an acknowledgement when model outcomes are unknown; immutable receipts make repeated control requests read-only. Scope or budgets cannot change. Task and per-role usage are cumulative; elapsed time is the measured active time persisted at boundaries, excluding outages, and each execution also enforces remaining time. Unknown transport duration is not an exactly measured wall-clock guarantee.

Typed report artifacts use the existing assistant-report-v1 schema; polling/cursor event replay and artifact reads preserve project/user isolation. The UI defaults to v2, polls queued/running tasks, displays cancel/continuation/unknown outcome controls and stores control UUIDs through uncertain transport/reload. Clarification retains M1's saved ask_user outcome; a separate input API, assistant threads, notes, approvals and writes remain later phases. Starting runner services does not authorize provider experiments; only explicitly submitted new tasks are eligible. This development round makes zero live provider calls.

## Verification

Focused87/1 skipped, full1036/12 skipped with95.42% coverage, native274, frontend143/build and desktop substitute acceptance passed; final affected backend16/1 skipped and frontend29/build passed. Business backup/recovery and fingerprint checks passed before applying0020 then0021. Runner CLI on the empty business queue and actual readiness200 passed. See PROJECT_ASSISTANT_M2.md for exact scope and limitations. The user's Agent executor selection persists. Frozen experiments/ledgers and human0% remain unchanged; real M2 quality is unmeasured.
