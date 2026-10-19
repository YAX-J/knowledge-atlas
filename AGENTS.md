# Knowledge Atlas Repository Instructions

[简体中文](AGENTS.zh-CN.md)

## Project purpose

Knowledge Atlas is a graduation project for a single developer. It organizes technical notes, code, project documents, and Git records into a temporal personal knowledge graph and uses evidence-grounded retrieval to answer questions.

The repository currently contains an interactive Mock demo graph, a real API-backed project/source workspace with separate desktop single-file and repository-scoped folder Markdown/Java upload plus relative-path persistence, Markdown parsing, bounded local Java source parsing with a derived type/field/method and same-file call outline plus repository-scoped cross-file `extends`/`implements` targets, leased recovery, DeepSeek candidate extraction with audited review, promotion into a scoped PostgreSQL graph, evidence-backed keyword/vector/one-hop hybrid retrieval, and synchronous non-persistent evidence questions with validated citations. Git-backed repository identity/synchronization, complete cross-file code semantics, entity disambiguation, question history, and multi-turn Agent behavior are not implemented. Derived code structure is not formal knowledge. Real DeepSeek quality and representative native pgvector acceptance remain separate from simulated tests.

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

## Repository skills

Task procedures live in `.agents/skills/`. Read the matching `SKILL.md` before starting work:

- Extraction, prompts, evidence validation → `.agents/skills/ka-extraction/SKILL.md`
- Review, promotion, graph reads → `.agents/skills/ka-review-promotion/SKILL.md`
- Models, Alembic, data shape → `.agents/skills/ka-migrations/SKILL.md`
- Verification and completion → `.agents/skills/ka-verify/SKILL.md`
- Upload, parsing, worker → `.agents/skills/ka-ingestion/SKILL.md`
- Vue workspace and graph UI → `.agents/skills/ka-frontend-workspace/SKILL.md`
- Bilingual docs, ADR, changelog → `.agents/skills/ka-docs-sync/SKILL.md`

Index: `.agents/skills/README.md`. Skills describe procedures; the rules in this file remain authoritative. Update the matching skill when behavior or workflow changes.

## Repository structure

- `frontend/`: Vue 3, TypeScript, Vite, Element Plus, and Mock data.
- `backend/`: FastAPI, SQLAlchemy models, Alembic migrations, and API tests.
- `docs/`: architecture, frontend, knowledge model, API, roadmap, setup, and ADR documentation.
- `.github/`: issue and pull request templates.
- `.agents/skills/`: repository-local agent skills for task procedures.
- `compose.yaml`: local PostgreSQL/pgvector, API, and parsing-worker services.
- `backend/app/worker.py`: independent database-backed parsing consumer; shares backend models and services.
- Planned but not yet created: prompt assets and experiment datasets.

## Non-negotiable domain rules

- Every generated knowledge item and answer must be traceable to source evidence.
- An LLM may propose candidates but must not write directly to authoritative business tables.
- PostgreSQL is the only current database and the source of truth for business data and graph storage. Neo4j is deferred; reintroduce a graph database only when measured needs justify it and record the decision in an ADR.
- Use stable business UUIDs for entities, relationships, and evidence. Never expose database-internal IDs through the API.
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
- Make ingestion and knowledge-persistence operations idempotent.
- Store secrets only in environment variables or a secret manager. Commit only `.env.example` files.
- Database migrations must be additive and reversible when practical.
- Keep request handlers thin; persistence and validation workflows belong in `backend/app/services/`.
- Preserve the temporary development user boundary until authentication replaces it deliberately.

## Verification

Before any verification, provide the user with concrete steps, commands, prerequisites, and expected results, then ask whether the user or the agent should execute them. Do not execute tests, builds, migration upgrade/downgrade checks, service smoke tests, browser walkthroughs, `git diff --check`, or equivalent validation commands until the user chooses the agent. An explicit choice in the current request counts; do not ask again.

Follow the chosen executor for that verification round. Mark the work as unverified until the selected checks pass or the user reports their results; never imply that a check passed merely because the implementation was reviewed statically.

For frontend changes, propose running from `frontend/`:

```bash
npm run build
```

For backend changes, propose running from `backend/`:

```bash
python -m pytest
```

For visible UI changes, include a real-browser walkthrough for desktop and mobile widths, covering keyboard focus, empty states, clipping, and panel scrolling.

For every change:

- Include `git diff --check` in the proposed verification steps.
- Confirm generated files, build output, dependencies, and secrets are not accidentally tracked.
- Report checks only when the agent actually ran them after the user's choice or the user supplied the results. Otherwise state that verification is pending.
- Add focused tests when a test harness exists; do not replace tests with manual inspection.

## Documentation responsibilities

- Update `README.md` only when installation, repository structure, status, or primary capabilities change.
- Update `docs/API_CONTRACT.md` when an API shape changes.
- Update `docs/KNOWLEDGE_MODEL.md` when entity, relationship, evidence, or temporal semantics change.
- Record material architecture decisions under `docs/adr/`.
- Keep `CHANGELOG.md` under the `Unreleased` section until a release is explicitly created.
- Clearly label planned behavior. Documentation must not imply that Mock behavior is production behavior.
- When a document has a `.zh-CN.md` companion, update both language versions in the same change and keep language links valid. Preserve command syntax, identifiers, and current/planned status across translations.

## Scope and safety

- Use the user's natively installed PostgreSQL (with pgvector) for local development and acceptance by default. Docker Compose is optional and must not be a prerequisite for real-service validation.
- Prefer the smallest vertical slice that advances the Markdown-to-evidence-answer workflow.
- Do not add team collaboration, complex permissions, IDE plugins, or large-scale deployment unless explicitly requested.
- Local commits at the end of completed turns are authorized by the user; follow the commit workflow below. Do not push, publish, deploy, rotate credentials, or modify external services without separate explicit user authorization.
- Preserve unrelated user changes in a dirty worktree.
- Never add real private repository content, access tokens, or personal secrets to fixtures, screenshots, logs, or documentation.

## Commit after each completed turn

- Unless the user explicitly requests otherwise, commit the completed changes from each conversation turn before sending the final response. This is standing authorization for local commits; do not ask for confirmation again.
- Prepare the checks appropriate to the changes, let the user choose the executor, synchronize relevant documentation, and review the staged diff before committing. Include only changes belonging to the completed work; preserve unrelated user changes.
- Use a concise commit message that describes the resulting behavior. Separate independent changes into focused commits when appropriate.
- If the turn makes no file changes, do not create an empty commit.
- If a required check fails or the commit cannot be created, preserve the work and report the failure instead of claiming completion or a successful commit.
- In the final response, report the commit hash or hashes and any remaining uncommitted changes. A local commit does not authorize pushing to a remote.

## Definition of done

A change is implementation-complete when its requested behavior and focused tests are implemented, documentation is synchronized, completed changes are committed according to the workflow above, verification steps and executor choice are recorded, and remaining limitations are stated. Call the change verified only after the agent-run checks pass or the user reports that their checks passed. Completing one roadmap phase does not authorize starting the next phase.
