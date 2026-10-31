# Project assistant M2

[简体中文](PROJECT_ASSISTANT_M2.zh-CN.md)

M2 is implemented and locally verified under [ADR0077](adr/0077-durable-assistant-execution.md). Business/source schema head is `20261031_0021`. M3–M5 remain planned; no live providers were called and real task quality remains unmeasured.

## Running and continuing tasks

The UI now submits `assistant-task-v2`, receiving202/queued without invoking a model. Run the separate consumer from backend with the existing environment:

```powershell
.\.venv\Scripts\python.exe -m app.assistant_runner
# Handle at most one queued task, then exit:
.\.venv\Scripts\python.exe -m app.assistant_runner --once
```

The native demo launcher and optional Compose stack include this runner separately from parsing. Only explicit new async_v2 tasks are eligible. Legacy v1 submissions stay synchronous200; old AgentRun records and source parser jobs are never consumed. A configured provider is used only when a user submits an eligible task; this implementation/verification does not authorize new provider experiments.

Each claim has a unique execution token and300-second lease. Model/tool attempts are reserved durably before transport. After each validated model decision or individual tool result, the attempt receipt, loop state and server reference pool commit together. A continued task skips completed steps, including tools inside a partially completed batch. Completed final decisions can publish an artifact after restart without another model call. Reports and artifacts commit together under the same ownership fence.

Failed/expired tasks never automatically requeue. Explicit continuation binds a unique request UUID to the exact task revision/checkpoint. Unknown model outcomes require acknowledgement; they remain counted and a further attempt may incur cost. Duplicate continuation UUIDs only read the saved outcome. Scope/budgets cannot increase. Model/role/tool counts remain cumulative. Time is measured active execution persisted at boundaries; unknown transport duration/outage time is not an exactly measured total wall-clock guarantee. Cancel prevents later steps/publication while in-flight requests may still complete and stay counted. Expired/stale workers cannot publish. Clarification retains a saved ask_user outcome and requires a new clarified goal; input/approval/write APIs are still deferred.

New business records: assistant_attempts, assistant_steps, assistant_artifacts and assistant_continuations. Checkpoints retain scoped user/tool content; operational events and attempt metadata do not contain prompts/tool bodies. Records remain with the project without automatic TTL/pruning; archival hides them, and physical project deletion cascades through owned records. No new deletion endpoint is provided. Checkpoints are limited to16 /200000 JSON characters each, alongside existing role/source/input/output/reference limits. Submission freezes knowledge time and source versions; execution rejects runtime/model/endpoint/tool-contract or source hash drift before a provider attempt.

## Observed verification, 2026-10-31

| Check | Result |
| --- | --- |
| Initial compatibility | Backend61; frontend26 passed |
| Expanded focused backend |87 passed /1 native-only skipped |
| Full backend coverage |1036 passed /12 skipped,95.42%; unchanged90% gate |
| Native PostgreSQL17.10 / pgvector0.8.7 |274 passed, including two-consumer row locking; isolated upgrade/downgrade/upgrade; owned schema cleaned |
| Frontend coverage/build |143 passed; lines75.60%, statements71.20%, branches64.26%, functions55.30%; existing gates/build passed |
| Final affected checks | Backend16 passed /1 native-only skipped after the OpenAPI assertion; frontend29/build passed after copy/layout changes |
| Startup configuration | PowerShell launcher AST and Compose YAML/API-runner provider-setting parity passed; Docker is unavailable locally, so container startup/hosted CI remains unverified |
| Delivery checks | Working/staged diff whitespace checks and local Markdown links passed; staged review excludes evaluation/data/backups/generated/dependency/environment artifacts and credential-pattern matches |
| Desktop Chrome1440x1000 | Queued/reload zero calls, background execution, unknown acknowledgement, continuation/replay, in-flight cancellation, exact scope/references, keyboard Space/Tab/Enter, empty project, project fencing and panel scroll passed; no page errors/horizontal overflow |

The desktop API used an owned native schema and the same runner service in a separate thread/session, with function-substituted models and blocked external HTTP transports. The actual runner CLI also exited successfully on the empty business queue. First report used2 models/3 tools and four source/code/knowledge references. A failed second model resumed to3 total models while keeping3 tools; repeating its continuation receipt held the global substitute counter at5. In-flight cancellation kept one attempt, no result/artifact and no late writes (counter6). A second recovery exercised Space/Tab/Enter (counter9); an empty project remained at9. UI reports the effective remaining coordinator budgets. Browser/API/runner/Vite and temporary schemas were cleaned. These are local engineering results, not hosted Linux/container CI or real-model quality.

Executed from backend: focused `pytest tests/test_assistant_execution.py tests/test_migrations.py tests/test_project_assistant.py tests/test_multi_agent.py tests/test_agent_progress.py tests/test_agent_tools.py tests/test_health.py`, one full `pytest --cov=app --cov-fail-under=90 --cov-report=term-missing --cov-report=xml:../output/m2-backend-coverage.xml`, and `python -m scripts.verify_native`. Fresh `--basetemp` paths were `../output/m2-focused-20261031-r2`, `../output/m2-full-20261031-r1` and `../output/m2-final-focused-20261031-r1`. Frontend ran `npm run test:coverage`, affected tests and `npm run build`. The user's Agent verification choice persisted; Windows TestClient/Vite checks ran outside the known sandbox restriction using existing dependencies.

## Business migration evidence

Verified backup and isolated restore of26 tables preceded0019→0020;25 existing business-table fingerprints were preserved. A fresh0020 backup/restoration of27 tables then preceded0021;26 existing business-table fingerprints were preserved. Both restore schemas were removed. Readiness returned200 with database/schema up. Private ignored backups are under `output/backups/pre-m2-20261031-01/` and `output/backups/pre-m2-0021-20261031-01/`; redacted migration JSON records are stored beside each manifest. Browser artifacts are local ignored files under `output/m2-browser-20261031/`. No backup/data/environment file is committed. Frozen evaluations/ledgers and human0% remain unchanged.
