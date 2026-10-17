# Knowledge Atlas Implementation Plan

This file identifies the active implementation phase and points to the detailed roadmap. It does not replace `docs/ROADMAP.md`.

## Current state

Completed:

- Repository purpose and graduation-project scope defined.
- Interactive Vue Mock frontend implemented.
- Desktop and mobile knowledge-graph workflows verified.
- Architecture, knowledge model, API draft, and development roadmap documented.
- Repository collaboration and decision-recording files initialized.
- FastAPI application, health endpoints, error envelope, and request IDs implemented.
- Project, Markdown source, and queued-task APIs implemented.
- PostgreSQL-oriented models, initial Alembic migration, and local service composition added.
- Backend interface tests implemented with an isolated SQLite database.
- Typed frontend API client foundation added while Mock remains the default.
- Explicit Markdown parsing tasks, persistent line-addressable chunks, and chunk pagination implemented.
- Identical-byte upload reuse, deterministic chunk IDs, idempotent task execution, and failed-task retry implemented.
- Frontend project creation/listing, source listing/upload, parsing/retry, source preview, and paginated evidence chunks integrated with real APIs while preserving the Mock graph.

## Active phase

The active phase remains the first Markdown ingestion vertical slice. API persistence, explicit parsing, and frontend project/source integration are complete in code; container connectivity and automatic task consumption remain.

Expected outcomes:

- Validate PostgreSQL, pgvector, and Neo4j services on a machine with Docker.
- Validate the integrated frontend project/source flow against PostgreSQL in the local container environment.
- Decide on automatic task consumption and recovery after validating explicit execution.

Acceptance criteria:

- Frontend and backend start independently from documented commands.
- Backend dependency health is observable.
- The frontend can create and query one project through the API.
- A queued Markdown task can progress through parsing and expose its chunks.
- Re-importing unchanged content has deterministic behavior.
- No model integration or graph extraction is required until parsing is stable.

## Later phases

1. Markdown parsing, chunking, and source locations.
2. Schema-constrained knowledge extraction and human confirmation.
3. Neo4j graph projection and real frontend data.
4. Keyword, vector, and graph hybrid retrieval.
5. Evidence-grounded Agent answers.
6. Code and GitHub ingestion.
7. Temporal evolution, governance, experiments, and deployment.

Detailed deliverables, risks, and twelve-week scheduling are maintained in `docs/ROADMAP.md`.

## Planning rules

- Work on one bounded phase at a time.
- Confirm architecture-impacting choices with an ADR.
- Keep acceptance criteria observable and testable.
- Update this file when the active phase changes, not after every small task.
- Do not mark a phase complete only because documentation or scaffolding exists.
