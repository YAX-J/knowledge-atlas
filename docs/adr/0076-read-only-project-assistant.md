# ADR 0076: Bounded read-only project assistant

[简体中文](0076-read-only-project-assistant.zh-CN.md)

- Status: Accepted; M1 locally verified with substitutes
- Date: 2026-10-31

## Decision

Implement M1 of the [project Agent plan](../PROJECT_AGENT_PLAN.md) using a fourth role, `project_assistant`, and the pinned LangGraph loop / existing DeepSeek adapter. Function calls express `call_tool`; strict final actions are `finish` and `ask_user`. Write/proposal and unknown actions/fields are rejected. No provider retry/fallback or external tracing upload.

Use separate `assistant-task-v1` requests and `assistant-report-v1` results. Add only `assistant_tasks` in reversible migration `20261031_0020`; preserve legacy AgentRun statuses, WorkflowRequest and QuestionRead. M1 brings the task envelope forward from M2 so refresh/replay is safe, but supplies no threads, independent attempt table, queue, runner, input, cancel, approvals or continuation. Workers never consume these records.

The server binds user/project, explicit ready source UUIDs/hashes, optional saved code snapshot and knowledge time. Empty source selection means confirmed knowledge only. Cap raw scope at 20 sources / 200000 UTF-8 bytes and 500 chunks / 240000 chunk characters; reject excess before transport. Exact local UUIDs never expand to latest versions. Selected code must uniquely belong to the selected repository snapshot. Historical knowledge requests exclude raw attachments.

Five read-only tools: `search_sources`, `read_source_chunk`, `search_knowledge`, `search_symbols`, `read_source_range`. Confirmed BM25 search reuses project/time isolation and at most 5 entities / 12 evidence items per search; embedding budget is zero. Raw/code tools only see selected versions. Content is untrusted data, never authorization. Searches return up to 8 excerpts; reads at most 60 lines / 4000 characters. Expose truncation and syntax warnings. A server-owned pool contains at most 32 reference IDs generated from actual returned text, source UUID/hash, optional exact chunk/formal evidence ID, path/lines and applicable selected commit. Raw source references cannot masquerade as formal evidence.

Task limits remain at most 8 model attempts / 16 tools; the single coordinator additionally permits 4 models / 8 tools / 230 seconds. Bound cumulative model input to 160000 characters, tool output to 24000 and report JSON to 16000. Generalize existing fenced `save_progress` with an explicit record model, retaining AgentRun as default. Persist reservations before callbacks and validated report checkpoints. Reject pending ORM writes; project archival, lease loss/expiry or progress failure prevents later calls/publication. Events contain only allowlisted metadata, while scoped business records retain user goals/artifacts.

Identical UUID submissions and all GET/poll/session restoration read saved state only. Changed input with the same UUID conflicts. Expired running tasks project as interrupted; transport failures may have unknown remote outcomes and remain counted. M1 has no implicit continuation. A new UUID is a separately submitted task. `ask_user` is a saved successful clarification outcome; the user submits a clarified new goal.

Reports have referenced/uncertain claims. Referenced claims require actual returned reference IDs; uncertainty requires missing information. Labels describe attached excerpts, not semantic correctness, verified tests or formal knowledge. Formal evidence answers remain evidence-claims-v3 with historical compatibility. UI separates draft and saved scope, displays provenance/usage/errors/clarification and exact navigation, uses text interpolation and restores per-project task IDs from sessionStorage. Existing workflow URL behavior is preserved.

## Consequences and verification

Source schema head becomes `20261031_0020`; the installed business database is not migrated automatically. Async reliability, notes and governed writes remain M2–M5. No new dependency, external write or paid experiment is authorized. Frozen inputs/results/ledgers and human coverage 0% remain unchanged; real M1 quality is unmeasured.

Added focused API/gateway/lease/replay, migration and Vue/composable regressions. The user selected Agent execution. Focused61, full backend1019/11 skipped (95.44%), native257, frontend140/coverage/build, desktop and final focused frontend26 passed. Diff/staging checks are recorded before commit. These are local engineering checks, not real-provider quality or hosted CI. [Commands and expected results](../PROJECT_ASSISTANT_M1.md) include full backend coverage >=90%, frontend coverage/build, disposable native PostgreSQL upgrade/downgrade/regression, desktop browser and diff/staging checks.
