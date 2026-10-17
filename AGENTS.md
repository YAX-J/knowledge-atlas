# Knowledge Atlas Repository Instructions

## Project purpose

Knowledge Atlas is a graduation project for a single developer. It organizes technical notes, code, project documents, and Git records into a temporal personal knowledge graph and uses evidence-grounded retrieval to answer questions.

The repository currently contains an interactive Mock graph, a real API-backed project/source workspace, FastAPI persistence APIs, and an explicitly executed Markdown parsing slice. Do not describe automatic task consumption, extraction, real graph projection, retrieval, or Agent capabilities as implemented.

## Read before changing code

Read only the documents relevant to the task, starting with:

- `README.md` for project scope and current status.
- `docs/ARCHITECTURE.md` for component boundaries and data ownership.
- `docs/FRONTEND.md` for the existing Vue frontend.
- `docs/KNOWLEDGE_MODEL.md` for entities, relationships, evidence, and temporal rules.
- `docs/API_CONTRACT.md` for the proposed frontend and backend boundary.
- `PLANS.md` and `docs/ROADMAP.md` for the active phase and future work.
- `docs/adr/` for accepted architecture decisions.

Do not treat the Word documents outside this repository as more current than the files above unless the user explicitly asks to reconcile them.

## Repository structure

- `frontend/`: Vue 3, TypeScript, Vite, Element Plus, and Mock data.
- `backend/`: FastAPI, SQLAlchemy models, Alembic migrations, and API tests.
- `docs/`: architecture, frontend, knowledge model, API, roadmap, setup, and ADR documentation.
- `.github/`: issue and pull request templates.
- `compose.yaml`: local PostgreSQL/pgvector, Neo4j, and API services.
- Planned but not yet created: a separate `worker/`, prompt assets, and experiment datasets.

## Non-negotiable domain rules

- Every generated knowledge item and answer must be traceable to source evidence.
- An LLM may propose candidates but must not write directly to Neo4j or authoritative business tables.
- PostgreSQL is the intended source of truth; Neo4j is a rebuildable graph projection.
- Use stable business UUIDs across stores. Never expose database-internal graph IDs through the API.
- `valid_from` and `valid_to` are properties, not graph relationship types.
- Temporal replacement direction is `new knowledge -[:SUPERSEDES]-> old knowledge`.
- Keep `user_id` and `project_id` boundaries even while the application is single-user.
- New entity or relationship types require a knowledge-model change and an ADR when the impact is architectural.

## Frontend conventions

- Use Vue 3 Composition API with `<script setup lang="ts">`.
- Keep TypeScript strict and avoid `any` unless an integration boundary makes it unavoidable.
- Put reusable domain types in `frontend/src/types.ts`.
- Keep demo fixtures in `frontend/src/mock/`; do not mix Mock records into components.
- Components should receive data through props and emit user intent. Keep page orchestration in `App.vue` until routing or a state store is justified.
- Preserve the technical-drawing visual language: cool paper background, dark teal ink, rose selection, amber project accents, and restrained motion.
- Maintain keyboard access, visible focus, reduced-motion support, and responsive behavior.
- Do not require the backend to return canvas coordinates. Layout is a frontend or view-preference concern.

## Backend conventions

- Use FastAPI with typed request and response models.
- Keep API, domain, persistence, and external model integrations separated.
- Validate LLM output against an explicit schema before persistence.
- Make ingestion and graph-projection operations idempotent.
- Store secrets only in environment variables or a secret manager. Commit only `.env.example` files.
- Database migrations must be additive and reversible when practical.
- Keep request handlers thin; persistence and validation workflows belong in `backend/app/services/`.
- Preserve the temporary development user boundary until authentication replaces it deliberately.

## Verification

For frontend changes, run from `frontend/`:

```bash
npm run build
```

For backend changes, run from `backend/`:

```bash
python -m pytest
```

For visible UI changes, also verify the affected flow in a real browser at desktop and mobile widths. Check keyboard focus, empty states, clipping, and panel scrolling.

For every change:

- Run `git diff --check`.
- Confirm generated files, build output, dependencies, and secrets are not accidentally tracked.
- Report checks that were actually run. Do not claim tests passed if they were not executed.
- Add focused tests when a test harness exists; do not replace tests with manual inspection.

## Documentation responsibilities

- Update `README.md` only when installation, repository structure, status, or primary capabilities change.
- Update `docs/API_CONTRACT.md` when an API shape changes.
- Update `docs/KNOWLEDGE_MODEL.md` when entity, relationship, evidence, or temporal semantics change.
- Record material architecture decisions under `docs/adr/`.
- Keep `CHANGELOG.md` under the `Unreleased` section until a release is explicitly created.
- Clearly label planned behavior. Documentation must not imply that Mock behavior is production behavior.

## Scope and safety

- Prefer the smallest vertical slice that advances the Markdown-to-evidence-answer workflow.
- Do not add team collaboration, complex permissions, IDE plugins, or large-scale deployment unless explicitly requested.
- Local commits at the end of completed turns are authorized by the user; follow the commit workflow below. Do not push, publish, deploy, rotate credentials, or modify external services without separate explicit user authorization.
- Preserve unrelated user changes in a dirty worktree.
- Never add real private repository content, access tokens, or personal secrets to fixtures, screenshots, logs, or documentation.

## Commit after each completed turn

- Unless the user explicitly requests otherwise, commit the completed changes from each conversation turn before sending the final response. This is standing authorization for local commits; do not ask for confirmation again.
- Run the checks appropriate to the changes, synchronize relevant documentation, and review the staged diff before committing. Include only changes belonging to the completed work; preserve unrelated user changes.
- Use a concise commit message that describes the resulting behavior. Separate independent changes into focused commits when appropriate.
- If the turn makes no file changes, do not create an empty commit.
- If required checks fail or the commit cannot be created, preserve the work and report the failure instead of claiming completion or a successful commit.
- In the final response, report the commit hash or hashes and any remaining uncommitted changes. A local commit does not authorize pushing to a remote.

## Definition of done

A change is done when its requested behavior is implemented, relevant validation passes, documentation is synchronized, completed changes are committed according to the workflow above, and remaining limitations are stated. Completing one roadmap phase does not authorize starting the next phase.
