# Knowledge Atlas Implementation Plan

This file identifies the active implementation phase and points to the detailed roadmap. It does not replace `docs/ROADMAP.md`.

## Current state

Completed:

- Repository purpose and graduation-project scope defined.
- Interactive Vue Mock frontend implemented.
- Desktop and mobile knowledge-graph workflows verified.
- Architecture, knowledge model, API draft, and development roadmap documented.
- Repository collaboration and decision-recording files initialized.

## Active phase

The next implementation phase is backend foundation and the first Markdown ingestion vertical slice.

Expected outcomes:

- FastAPI application skeleton and health endpoint.
- PostgreSQL, pgvector, and Neo4j local development services.
- Environment configuration and database migrations.
- Project, source, task, and candidate-knowledge persistence models.
- Frontend API client foundation without removing the Mock fallback.

Acceptance criteria:

- Frontend and backend start independently from documented commands.
- Backend dependency health is observable.
- One project can be created and queried through the API.
- One Markdown file can be uploaded and represented as a queued processing task.
- No model integration or graph extraction is required until the foundation is stable.

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
