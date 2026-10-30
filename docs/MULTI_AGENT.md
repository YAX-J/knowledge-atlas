# Scoped agents in one project

Claim-level answers are implemented in [ADR 0069](adr/0069-answer-claim-evidence.md): `evidence-claims-v2` binds each supported claim to current scoped evidence, marks insufficient claims separately and supports exact source navigation. The server derives legacy flat fields; old records remain readable without inferred attribution or new provider calls. Structural validation does not establish semantic entailment. Frozen experiments, the 84/61 provider ledger and schema head `20261029_0019` remain unchanged; human grading is deferred.

[简体中文](MULTI_AGENT.zh-CN.md)

Knowledge Atlas now contains three registered agents and two explicit LangGraph workflows in the existing backend. The Vue frontend, FastAPI application, database, Worker and dependency environments remain shared. No second application or nested Agent project is created. See ADR [0064](adr/0064-scoped-agent-modules.md), [0065](adr/0065-durable-reviewed-workflows.md) and [acceptance results](MULTI_AGENT_ACCEPTANCE.md).

## Repository layout

```text
knowledge-atlas/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── base.py, registry.py, runtime.py
│   │   │   ├── loop.py, graph_runtime.py
│   │   │   ├── code_analysis/       # agent, immutable context, analysis engine
│   │   │   ├── knowledge_extraction/
│   │   │   └── evidence_qa/
│   │   ├── workflows/              # contracts, state, routing, two pipelines
│   │   ├── tools/                  # repository, chunks, scoped evidence tools
│   │   ├── llm/                    # prompts.py, usage.py, providers/deepseek.py
│   │   ├── analysis/               # syntax parsers, bindings, compiler adapter
│   │   ├── services/               # application transactions and scope checks
│   │   ├── api/routes/agents.py
│   │   └── models/agent_run.py
│   ├── scripts/                    # existing compiler helpers and acceptance tools
│   ├── migrations/versions/20261029_0019_agent_workflows.py
│   └── tests/test_multi_agent.py, test_agent_tools.py
├── frontend/src/
│   ├── pages/AgentWorkspace.vue
│   ├── components/agent/           # result and event presentation
│   ├── composables/useAgentRuns.ts
│   └── api/agents.ts
└── docs/
```

Old `services` import paths for moved parsers, provider, usage, code engine and repository loop remain module aliases. Existing routes and monkeypatch seams retain the same module objects. These compatibility files should not acquire a second implementation. Prompt text/version values are moved without changing legacy prompt behavior. Java/TypeScript/Go helper programs remain under `backend/scripts` and use the existing project dependencies.

## Agents and workflows

| Agent | Inputs and tools | Output boundary |
| --- | --- | --- |
| `code_analysis` | Server-selected immutable source versions; existing single-step, bounded repository tools or explicit native static analysis | Validated derived call decisions, actual context and truncation; no formal graph writes |
| `knowledge_extraction` | Authorized chunk metadata, `read_chunk`, optional validated code findings as hints | Structured candidates validated against exact source chunks by the existing extraction service |
| `evidence_qa` | Confirmed project/time-scoped evidence; `search_knowledge`, `read_evidence`; optional code navigation hints | Citation IDs checked against retrieved formal evidence; empty evidence refuses before a model call |

`knowledge_pipeline`: optional code analysis → chunk-reading extraction → persist candidates → `awaiting_review` → existing explicit human review → explicit resume → `succeeded`. Code findings never substitute for source quotations. All saved candidate IDs must still exist in the same source/task and be confirmed or rejected before resume. Resume does not invoke models, embeddings or automatic indexing. Rejected candidates are a legitimate completed human decision.

`question_pipeline`: optional code analysis → scoped retrieval/tool-reading QA → validated answer → `succeeded`. Derived code results are navigation hints; claims require formal evidence. Historical questions reject current-code hints. The new workflow defaults to offline `bm25`; legacy question and conversation defaults are preserved. Workflow answers are stored in the run; the existing conversation feature remains a separate entry point.

The initial coordinator is sequential because these steps have explicit dependencies. This implements bounded tool loops and coordinated roles, not arbitrary autonomous task generation. To add an agent, implement its input/context boundary, register it, expose only scoped tools, and add an explicit workflow edge plus scope/budget tests. Do not add a new provider client or another application.

## Runtime, persistence and API

Install updated backend dependencies in the existing environment with `.\.venv\Scripts\python.exe -m pip install -e ".[dev,evaluation]"`; LangGraph is pinned in `backend/pyproject.toml`. Back up existing data before `alembic upgrade head`. Migration head is `20261029_0019`, adding `agent_runs`. Readiness requires that table and the expected schema version. It never migrates automatically.

Shared context carries user/project/source/snapshot/time/run IDs. Each role is limited to four model turns/eight tools; a whole run defaults to at most eight model attempts, sixteen tool calls and four embedding attempts. Failed provider attempts count. Limits may be lowered to zero. Extraction/QA have bounded input/output text, source/chunk IDs, deadlines and strict JSON schemas. No shell or file-write tool is exposed. Agent/tool events contain identifiers from a fixed vocabulary and numeric metadata, without prompts, raw tool arguments or chain of thought. Saved results contain authorized business evidence as before. LangGraph tracing upload is explicitly disabled for these invocations.

API paths below are relative to `/api/v1`:

| Method | Path | Behavior |
| --- | --- | --- |
| POST | `/projects/{project_id}/agent-runs` | Explicit synchronous execution; caller supplies `request_id` UUID |
| GET | `/projects/{project_id}/agent-runs?page=1&page_size=10` | Project-scoped paginated history (page size 1–50) |
| GET | `/projects/{project_id}/agent-runs/{run_id}` | Saved status/result/events/usage/review counts; no providers |
| POST | `/projects/{project_id}/agent-runs/{run_id}/resume` | Recheck saved human decisions, finish without providers |

```json
{
  "request_id": "UUID",
  "kind": "knowledge_pipeline",
  "source_id": "UUID",
  "include_code_analysis": true,
  "code_strategy": "tools",
  "model_limit": 8,
  "tool_limit": 16,
  "embedding_limit": 4
}
```

Question input uses `kind=question_pipeline`, a trimmed 1–200 character `question`, optional timezone-aware `valid_at`, and `retrieval_mode` from `bm25|bm25_source|rrf|hybrid|vector`. Code context accepts either `snapshot_id` or up to 99 unique `version_ids`, with a code source and `include_code_analysis=true`. Knowledge input requires a ready source, no question and no historical time. Unknown fields and out-of-bound budgets fail validation. Scope errors return 404. A conflicting request UUID returns `WORKFLOW_REQUEST_CONFLICT` (409); pending review returns `WORKFLOW_REVIEW_PENDING` (409).

The run row is claimed and committed before providers. Same UUID/same input reads the saved run without repeating providers; different input conflicts. Each execution is fenced by its execution UUID/lease. Expired running records are read as `interrupted`, without automatic paid retry. Under [ADR 0067](adr/0067-durable-agent-progress.md), each event saves metadata and usage; model/tool/embedding reservations commit before callbacks. Active ownership is required and the lease is renewed at these boundaries. Validated code/answer results and committed extraction candidate IDs are saved at step checkpoints; later failures retain earlier results. GET can read committed progress during a synchronous POST. There is no event stream or automatic crash-node continuation. Existing extraction idempotency also applies: a previously successful extraction for the same source/strategy reuses its candidates. Extraction status reads show the most recently created legacy/tool task; legacy extraction POST still uses its original strategy.

Progress persistence refuses pending ORM writes and never flushes unfinished candidates. A persistence failure (`WORKFLOW_PROGRESS_UNAVAILABLE`) or lost ownership (`WORKFLOW_INTERRUPTED`) prevents later callbacks. A pre-call reservation may conservatively count a request that was never sent, so usage is not a billing receipt. Only successfully committed checkpoints survive a process crash; extraction commit and the run checkpoint remain separate transactions. The top-level run status remains authoritative even when a partial result contains a step status. Interrupted tasks remain readable and do not become resumable paid executions by GET/replay.

## Batched workflow list reads

`GET /projects/{project_id}/agent-runs` validates the active user/project once, counts and loads the requested page, then reads candidate ID/source/task/review-status projections for that page in one query. It does not load candidate payloads, names or summaries. Counts are matched to each run's exact unique candidate IDs and source/task under the fixed user/project scope, so reused extractions and overlapping or missing ID subsets retain detail-read behavior. Empty/candidate-free pages skip the candidate query.

List and detail use the same response projection, preserving partial results, usage, saved scope and read-only lease expiry. The page refreshes existing ORM objects and uses one current instant to classify all expired leases. Ordering remains `created_at DESC, id ASC`; defaults remain page1/size10, maximum50. Response shape, migration head `20261029_0019`, detail/resume review checks and provider replay rules are unchanged. Total/page/count reads remain separate statements; this does not promise an atomic cross-statement snapshot.

The regression `backend/tests/test_agent_list_performance.py` reproduces the old list path and compares the full response while instrumenting SELECTs over synthetic envelopes. Pages of 1/10/50 tasks with candidate IDs use 4 queries instead of 6/33/153; empty/candidate-free pages use 3. This is a query-count result, not a measured HTTP latency or production-capacity claim. It covers tied pagination, exact subsets, scope denial, stale ORM state and lease boundaries; native acceptance includes the same file. No provider calls or frontend changes are needed for these checks.

Validation on 2026-10-30: focused43 passed; full backend783 passed/8 skipped, statement coverage95.58% with KA_NATIVE_COMPILERS=1; native PostgreSQL17.10/pgvector0.8.7 acceptance205 passed with migration upgrade/downgrade/upgrade. The disposable native schema was removed and the application migration marker stayed unchanged. Both SQLite and native PostgreSQL asserted the same query counts and complete response equivalence. No provider calls were made. Frontend/build/browser checks were not run for this backend-only change.

## Using the workspace

Open a ready source in “资料与审核”, then “协作任务”. Choose knowledge or question flow; code analysis is optional. The page shows the source, request limit, costs notice, saved results, actual code context and event trace. Under [ADR 0068](adr/0068-explicit-workflow-scope.md), choose BM25/source-aware BM25/RRF/hybrid/vector and an optional browser-local knowledge time, submitted as an aware UTC instant. BM25 remains the default. Historical questions disable and clear current-code analysis. Enabling code analysis reads the existing analysis-contexts endpoint and exposes a fixed snapshot or explicit local overrides (up to 99); the main file keeps its opened immutable version, while unspecified local related files use their latest parsed version at execution. Loading/failed/invalid context reads block submission and offer read-only retry. The draft preview is separate from the selected task's saved scope. After extraction, open the source review, confirm/reject the named candidates, return to the task, refresh, then resume. Questions show validated evidence links into the existing source viewer.

Start/list/read/resume responses add an allowlisted `scope` object: retrieval_mode, valid_at, include_code_analysis, code_strategy, snapshot_id, version_ids. Unused question/code fields are null or empty; the raw request, source hash and prompts are not exposed. Client types tolerate absent/null scope from older servers. Drafts are not restored from saved scope or replayed on reload. Context choices reset on source changes; project changes also clear question/time/retrieval drafts. Truncated metadata remains explicit, and the backend still validates scope/bytes/source budgets before compiler/provider calls.

`#/agents?project=UUID&source=UUID&run=UUID` restores by GET. Pending request UUIDs survive reload in session storage; an unknown transport result must be read before an explicit same-UUID resend. Project changes/disposal invalidate late UI results. Running records are polled by GET every three seconds. No reload or poll submits a new model request.

## Acceptance limits

Focused and full tests use provider substitutes, with native compiler and PostgreSQL checks separate from actual model quality. The local browser workspace has its own temporary schema and synthetic provider protocol. No new paid experiment is performed for this refactor; the existing cumulative ledger stays at 84 model /61 embedding attempts. Genuine human blind grading remains assigned to the user. Private GitHub, Docker and remote CI acceptance retain their previously documented limits.
