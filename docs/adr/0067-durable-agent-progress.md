# ADR 0067 Durable agent progress and validated step checkpoints

[简体中文](0067-durable-agent-progress.zh-CN.md)

- Status: Accepted
- Date: 2026-10-30
- Supersedes the end-only event/usage persistence in ADR 0065. Scope, explicit human review, synchronous execution and read-only replay remain.

## Decision

Keep the existing `agent_runs` schema (`20261029_0019`) and endpoint shapes. `RunContext` accepts an application-owned progress callback; agents never receive a database Session. Every event saves content-free metadata and usage. Model/tool/embedding reservations commit before the underlying callback, including attempts that subsequently fail. Updates require matching user/project/run/execution UUID, running status, an active lease and a non-archived project. Renew the 1200-second lease at these event boundaries; retain the existing bounded runtime and per-role/global budgets.

`services/agent_progress.py` commits at boundaries where the shared request session has no new/dirty/deleted ORM writes, and disables autoflush around the progress update. Refuse pending writes rather than incidentally committing unfinished business data. Extraction already commits its claim before providers and persists only validated candidates afterward; checkpoints preserve that transaction boundary. Database failures are mapped to content-free `WORKFLOW_PROGRESS_UNAVAILABLE`; lost ownership uses `WORKFLOW_INTERRUPTED`. Disable the failed sink and refuse later call reservations. Agent context restoration also covers failures in the initial progress callback.

Save code analysis only after existing validation, extraction task/candidate IDs after their successful commit, and answers only after citation validation. Events identify these snapshots as `code_checkpoint`, `extraction_checkpoint`, `answer_checkpoint` with `saved` status. Later workflow failures keep these partials instead of replacing them with null. Localize the displayed checkpoint labels. The run's top-level status remains authoritative; a partial's internal step status does not establish workflow completion.

## Consequences and limits

GET can observe committed progress during a synchronous POST. Once its lease expires, an interrupted run still exposes saved usage/events/results; reading, same-UUID replay and existing review resume issue no provider calls. These are inspectable checkpoints, not automatic paid node continuation, event streaming or a background task queue. A long blocked callback has no independent heartbeat. Pre-call reservation can conservatively count an unsent request and does not establish exact billing or exactly-once provider delivery. Only committed checkpoints survive a process crash; candidate commit and the extraction checkpoint remain separate transactions. No schema migration or new provider experiment is needed.

## Verification

The user's prior Agent-execution choice was retained for this continuation. Actual checks on 2026-10-30:

- Focused progress/coordinator/tools/extraction/question/conversation tests: 55 passed.
- Full backend with `KA_NATIVE_COMPILERS=1`: 746 passed, 8 opt-in external/native cases skipped, statement coverage 95.25% (90% gate).
- PostgreSQL 17.10 / pgvector 0.8.7: 169 passed in the owned schema, including migration roundtrip and a separate-connection observer reading the model reservation while a provider substitute blocks. The schema was removed; the application migration marker was unchanged.
- Frontend: 116 tests across 16 files, configured statement/line coverage 68.66%/73.42%, type checking and production build passed.
- Desktop Chrome, named agent-browser session, ports 8011/5181: empty task history, explicit local-stub extraction, review pause, refresh restoration, compiler-plus-QA, three localized checkpoint labels, keyboard focus and event-panel scrolling checked. No horizontal overflow or alerts. Browser and dedicated services closed; the browser schema was removed. Screenshots remain in ignored local output.

Checks use local provider substitutes/public fixtures; no new real-provider requests or human quality scores. Historical acceptance and frozen evaluation files remain unchanged. Whitespace review and 288 local Markdown targets passed. Dedicated ports 8011/5181 were confirmed released; screenshots/build output are ignored and excluded from the commit.
