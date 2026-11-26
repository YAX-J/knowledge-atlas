# Knowledge Atlas

Hybrid search now uses BM25 for Chinese and mixed-language lexical recall and records a versioned protocol alongside saved answer retrieval summaries. Default search and RRF remain unchanged. A paired native benchmark retained the 200-record batch after mixed performance results. [Retrieval decision](docs/adr/0087-hybrid-bm25-protocol.zh-CN.md)

Semantic index updates now save each validated batch with its progress. A later explicit update reuses matching vectors after a failure; status reads never resume work. Partial batches are searchable with potentially incomplete coverage. [Batch recovery](docs/adr/0086-persisted-embedding-batches.zh-CN.md)

Long documents support a free batch plan followed by explicit confirmation of up to eight extraction requests. Results are validated and published as pending candidates atomically; failures are never automatically retried. [Batch extraction](docs/adr/0085-bounded-batch-extraction.zh-CN.md)

[简体中文](README.zh-CN.md)

Knowledge Atlas is a graduation project that organizes a developer's technical notes, code, and repository history into a temporal personal knowledge graph. The frontend opens the project graph. To add knowledge, open **Project notes**, save a Markdown revision, and select **Analyze note and extract knowledge**. Review each candidate against the original text before adding it to the graph. Search results, historical graph views, and answers can then lead back to the supporting evidence.

The frontend uses Vue 3, the API uses FastAPI, and PostgreSQL with pgvector stores project data. The optional Neo4j projection supports explicit snapshot synchronization, one- and two-hop neighborhoods, and evidence navigation. [Neo4j setup](docs/DEVELOPMENT_SETUP.zh-CN.md#可选的-neo4j-图谱快照)

Local uploads with relative paths now deduplicate by path and content: identical bytes at different paths keep separate sources, while repeated uploads at the same path reuse the task. Unlocated single-file uploads retain content deduplication; lost historical paths require re-upload. [Source identity](docs/adr/0083-path-aware-source-ingestion.zh-CN.md)

The real graph supports deterministic topology and directed layouts, pointer or Alt+arrow node movement, relationship filtering, and shortest undirected association highlighting within the loaded subgraph. Positions are local view state; arrows keep their original direction. [Graph interaction](docs/FRONTEND.md)

Projects can be edited, archived and restored; source archiving preserves original evidence. Saved conversation claims support immutable issue feedback without rewriting answers or knowledge. Source head is now `20261126_0024`, adding two tables. Existing databases are not automatically migrated: back up, verify an isolated restore, then run `alembic upgrade head`. [Library and feedback](docs/adr/0084-library-archiving-answer-feedback.zh-CN.md)

## Current capabilities

| Area | What you can do |
| --- | --- |
| Notes and sources | Edit Markdown notes, revisit immutable revisions, and analyze a fixed revision. Import Markdown, supported source code, local folders, GitHub commit snapshots, and versioned issues, pull requests, reviews, and threads. |
| Candidate review | Verify structured candidates against exact excerpts. Review proposed validity intervals and primary database replacements before committing them to the graph. |
| Graph and governance | Open the graph on startup, switch projects from the top bar, and explore entities, relationships, evidence, and historical snapshots. Inspect replacement chains and grouped changes, manage aliases and merges, restore or withdraw knowledge, and check for conflicts. |
| Search and Q&A | Use keyword, BM25, source-aware BM25, vector, hybrid, or RRF retrieval. Ask about a historical instant or compare an approved database cutover. Saved answers link each supported claim to its evidence and, where applicable, its relationship and validity interval. |
| Code analysis | Inspect syntax, static call candidates, and compiler-backed Java, TypeScript, and Go declarations. Select a pinned commit or local source version when paths repeat. Analysis is read-only and does not execute user code or build scripts. Scan limits and truncation are reported. |
| Workbench | Browse live project data in the six-module deck, use the command palette to navigate, or open the separate mock demo. A workspace URL can restore a project, source, graph selection, historical instant, or conversation. |
| Agent workflows | Use the three specialist roles, two fixed LangGraph workflows, or the asynchronous project assistant. Tasks save their input scope, usage, and checkpoints. Proposed edits require explicit approval, with the option to cancel or explicitly continue. |
| Verification | Run migration checks, backup and restore drills, native PostgreSQL acceptance, offline evaluations, and synthetic performance benchmarks. |

The project assistant can import and parse an entire GitHub repository in batches pinned to a commit, then generate a report citing the files it selected and read. [Repository import setup](docs/DEVELOPMENT_SETUP.zh-CN.md#github-快照导入), [whole-repository assistant tasks](docs/PROJECT_ASSISTANT_M34.zh-CN.md#整仓助手任务)

BM25 and source-aware BM25 process up to 50,000 visible entities in batches of 200, with up to 32 pieces of ranking evidence and 4,000 ranking characters per entity. The response reports the match count and a separate truncation flag. RRF uses the same BM25 implementation for its lexical branch. [ADR 0066](docs/adr/0066-batched-global-lexical-retrieval.zh-CN.md)

Agent runs retain the selected retrieval method, historical instant, and code version. The original collaborative workflows save committed steps and attempt counts for read-only recovery after interruption. Their saved records do not automatically resume unfinished steps. The project assistant has a separate asynchronous runner with explicit cancellation and continuation. [Durable workflow progress](docs/adr/0067-durable-agent-progress.zh-CN.md), [workflow input scope](docs/adr/0068-explicit-workflow-scope.zh-CN.md)

## Run locally

Install Python, Node.js, and PostgreSQL with pgvector. Configure `backend/.env` and back up any existing database before a migration. The current source migration head is `20261126_0024`; existing databases are not automatically upgraded. The readiness check reports databases that are behind or missing required tables or columns. [Environment setup](docs/DEVELOPMENT_SETUP.zh-CN.md), [backup and restore](docs/BACKUP_RESTORE.zh-CN.md)

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,evaluation]"
cd ..\frontend
npm ci
cd ..
.\scripts\start-demo.ps1 -Seed
```

Reuse the virtual environment if it already exists. Startup and read-only status checks do not call model providers. Extraction, Q&A, Agent execution, and semantic index updates require explicit actions. [Demo, worker, and Docker commands](docs/DEMO.zh-CN.md)

## Verification status

- The synchronous and asynchronous project assistant flows, revisioned notes, and approval paths were validated with local substitutes. The migration to `0023` followed a verified backup and isolated restore, with all 30 existing business-table fingerprints preserved. [M2 report](docs/PROJECT_ASSISTANT_M2.zh-CN.md), [M3/M4 report](docs/PROJECT_ASSISTANT_M34.zh-CN.md)
- M5 has a frozen 20-task development set, an 18-check acceptance matrix, a zero-call preflight, and a report import workflow. Live execution, fixture replay, quality evaluation, and release remain pending. [M5 status](docs/PROJECT_ASSISTANT_M5.zh-CN.md)
- Current answers use evidence-claims-v3. The server derives overall support from individually cited claims. Historical records keep their original format. Offline judges support OpenRouter Jev, direct TypeSafe Jev, and native Cloudflare Workers AI. Human grading coverage remains at 0%. [Claim support contract](docs/adr/0075-server-derived-answer-support.zh-CN.md), [holdout-v3 corpus](evaluation/holdout-v3/README.zh-CN.md), [historical judge run](evaluation/results/2026-10-31-holdout-v3-clef-run1/REPORT.zh-CN.md)
- The holdout contains seven commit-pinned public technical documents and 24 questions, separate from the development set. The historical 457-call judge run scored v2 outputs. The v3 claim validation used an independent synthetic development set. [Development checks](evaluation/development/claim-support-v3/README.zh-CN.md), [OpenRouter guide](docs/OPENROUTER_EVALUATION.zh-CN.md), [Cloudflare guide](docs/CLOUDFLARE_EVALUATION.zh-CN.md)
- Earlier public experiments recorded 84 model and 61 embedding attempts. Local substitute checks add no provider calls. Private repository access, full restore permissions, and hosted CI and Docker acceptance depend on the environment. [Public experiment report](evaluation/results/2026-10-26-public-v2-run1/REPORT.zh-CN.md), [earlier acceptance and optimization](docs/OPTIMIZATION_20261029.zh-CN.md)
- The single-user demo has no production authentication. Team collaboration, webhooks, IDE extensions, and large-scale deployment are outside the project scope.

## Documentation and repository

`frontend/` contains the workbench. `backend/` contains the API, workers, migrations, and verification scripts. `evaluation/` contains frozen corpora, results, and performance reports. Supporting documentation is in Chinese.

- [Backend commands](backend/README.zh-CN.md), [frontend structure](docs/FRONTEND.md), and [system architecture](docs/ARCHITECTURE.md)
- [API contract](docs/API_CONTRACT.md), [knowledge model](docs/KNOWLEDGE_MODEL.md), and [architecture decisions](docs/adr/README.zh-CN.md)
- [Agent workflows](docs/MULTI_AGENT.zh-CN.md), [evaluation guide](evaluation/README.zh-CN.md), and [performance measurements](evaluation/performance/2026-10-29-scale/README.zh-CN.md)
- [Current plan](PLANS.zh-CN.md), [roadmap](docs/ROADMAP.md), [changelog](CHANGELOG.zh-CN.md), and [historical documentation](docs/archive/pre-optimization-20261029/README.md)
- [Proposed project-wide Agent redesign](docs/PROJECT_AGENT_PLAN.zh-CN.md)
