# ADR 0004 Database-backed parsing worker with execution leases

- Status: Accepted
- Date: 2026-10-17

## Context

The explicit parser and frontend ingestion flow are implemented. Queued uploads still need an operator to start parsing, and a process interruption can leave a task running forever. PostgreSQL already owns task state; a separate broker would add deployment scope before extraction is stable.

## Decision

- Add an optional independent `python -m app.worker` process that polls persisted parsing tasks. `--once` handles at most one eligible task and exits for verification and scheduled invocations.
- Scope a worker to one user UUID (the development user by default). Only process sources and active projects with matching user/project boundaries. Accept `markdown_parsing` and legacy `knowledge_extraction` upload tasks; neither performs model extraction.
- Share execution logic between the worker and the existing explicit run endpoint. Claim tasks with a conditional database update, a fresh execution UUID, an incremented attempt counter, and a finite lease. No broker or in-process API background task is introduced.
- Workers consume queued tasks and recover running tasks whose leases expired. Legacy running tasks without a lease use their start/update time as the timeout baseline. Normal failures remain failed until an explicit retry. Expired tasks at the configured attempt limit become failed instead of retrying indefinitely.
- Fence both success and failure writes with the execution UUID and running status. Commit chunks, source state, and final task state in one transaction. A replaced execution cannot overwrite a newer result, even if the old process resumes or fails late.
- Preserve manual execution for queued/failed tasks and its HTTP response shape. An active or expired running task remains a conflict for the manual endpoint; the worker performs timeout recovery.

## Consequences

Worker startup enables automatic parsing without changing upload acceptance. The UI can refresh task state and retains manual controls when no worker is running. Leases are fixed and configurable (default 300 seconds); there is no heartbeat or preemptive cancellation. A live parser exceeding its lease can overlap a replacement in computation, but only the current execution can persist results. Operators should size leases above normal parsing duration. Automatic attempts default to three; explicit failed-task retries remain allowed beyond that count.

SQLite tests can exercise fencing and independent sessions, but do not establish PostgreSQL contention behavior. Docker/PostgreSQL integration remains a separate validation requirement. Future extraction jobs may require heartbeats and a different execution duration policy.

## Alternatives considered

API background tasks do not survive API restarts. Celery/RQ plus a broker would add unnecessary dependencies for the current single-user parsing slice. Resetting running tasks indiscriminately on startup could steal work from another live worker and allow stale results to overwrite new ones.
