# Multi-agent implementation work

Authorized: refactor the existing single Knowledge Atlas project into three scoped agents and two explicit coordinating workflows. Preserve existing endpoints, human-only graph writes, immutable evidence, and cumulative provider experiment budget (84/61 of120/160 already used). No real provider acceptance this turn.

Verification executor: Agent, standing user authorization. Focused pytest, final full backend with native compilers/90% coverage, native disposable-schema workflow/migration checks, frontend coverage/build, desktop browser when UI changes, diff/staged/frozen data checks and local commit. Existing backend venv, frontend dependencies and native PostgreSQL/pgvector are prerequisites. Expected: old behavior compatible and new workflows respect scope, budgets, idempotency and human review. Back up before applying any additive migration to the application.

- [x] Reorganize models/prompts/parsers/tools and retain compatibility imports.
- [x] Shared scoped context, agent registry, budgets and numeric events.
- [x] Code, extraction and evidence-QA agents with bounded tool loops.
- [x] Durable knowledge/question workflows with explicit human-review resume.
- [x] API/frontend workflow controls, polling and trace display.
- [x] Focused/full/native/browser verification, bilingual docs and local commit.

Final checks: backend723 passed/7 opt-in skips,95.19%; native145 passed and migration roundtrip; frontend116 passed and production build; desktop human-checkpoint/QA/code/evidence flow; application backup/schema restore/upgrade0019 preserves24 old business tables.10 module aliases and legacy prompt constants verified; evaluation unchanged. See [acceptance](MULTI_AGENT_ACCEPTANCE.md). Local commit records this completed work; no push is authorized.
