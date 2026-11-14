# Knowledge Atlas Backend

Whole-repository assistant tasks run through `python -m app.assistant_runner`. See the [task and progress contract](../docs/PROJECT_ASSISTANT_M34.md#whole-repository-assistant-tasks).

Optional Neo4j endpoints check connectivity, sync one project's formal graph snapshot, and read its bounded neighborhood through Cypher. Graph reads include the snapshot time and whole-project totals. See the [setup guide](../docs/DEVELOPMENT_SETUP.md#optional-neo4j-graph-snapshots) and [API contract](../docs/API_CONTRACT.md#neo4j-项目快照).

M5 offline preparation (2026-10-31): a sealed independent20-task development packet,18-check acceptance matrix, zero-call preflight, reported-run/grade adapter and repeatable local engineering command are implemented. M5 overall remains pending the authorized live executor/fixture replay, real quality, hosted CI, demonstration and release. No real provider calls or business migration; schema stays0023 and historical evaluations/grants/ledgers stay unchanged. See [M5 status and runbook](../docs/PROJECT_ASSISTANT_M5.md).

M2 is locally verified and the business database is migrated to source head20261031_0021. Start `python -m app.assistant_runner` separately from parsing; `--once` exits after at most one queued async_v2 job. The UI uses asynchronous202 assistant-task-v2; legacy v1 remains synchronous200. Checkpoints/attempts/artifacts, cancellation and explicit version-bound continuation follow [ADR0077](../docs/adr/0077-durable-assistant-execution.md); [commands/results](../docs/PROJECT_ASSISTANT_M2.md). No live quality claim, provider calls or M3–M5 implementation. Earlier M1/head notices below describe historical rounds.

Read-only project assistant M1 is implemented and locally verified with substitutes; see [usage/checks](../docs/PROJECT_ASSISTANT_M1.md) and [ADR0076](../docs/adr/0076-read-only-project-assistant.md). Source schema head is now `20261031_0020` (assistant_tasks only); the business database has not been automatically migrated. New assistant/tasks endpoints and typed reports are separate from legacy agent-runs and QuestionRead. No live calls; M2–M5 remain planned. Older schema announcements below describe their original changes.

Offline anonymous judging supports OpenRouter Jev, direct TypeSafe Jev and native CF adapters. Configure EVALUATION_PROVIDER=openrouter, local OPENROUTER_API_KEY, OPENROUTER_MODEL=typesafe/jev-1.14 and OPENROUTER_TIMEOUT_SECONDS=60. Existing credentials remain. No live calls this turn; human grading coverage0%. See [OpenRouter commands](../docs/OPENROUTER_EVALUATION.md), [CF](../docs/CLOUDFLARE_EVALUATION.md) and [Jev](../docs/JEV_EVALUATION.md).

[ADR 0075](../docs/adr/0075-server-derived-answer-support.md) implements `evidence-claims-v3`: providers return only confidence, claims and missing_information; the backend derives API supported from all claim statuses. Citation attribution, missing information, budgets and project scope stay strict. v2 and flat history read/replay saved values without recomputation or provider calls; v2 is never a new-output fallback. Independent fictional development cases check structure/compatibility, not live v3 quality. Frozen v2 experiments/ledgers/scores and schema head `20261029_0019` remain unchanged; human coverage0%.

Scoped multi-agent workflows now share this application. Update the existing environment with `.\.venv\Scripts\python.exe -m pip install -e ".[dev,evaluation]"` from backend; this installs pinned LangGraph. Back up/rehearse recovery before `alembic upgrade head` to `20261029_0019`. See [roles, API and synchronous human-review boundaries](../docs/MULTI_AGENT.md).

[简体中文](README.zh-CN.md)

Current behavior is specified by the optimization report and ADR 0060–0063; migration head `20261029_0019`. Historical checkpoint announcements have been archived. [验收 / Acceptance](../docs/OPTIMIZATION_20261029.md)

## Current context and runtime checks

Workflow reads now project an allowlisted `scope` from the saved request: retrieval/time, code flag/strategy and snapshot/local-version IDs. The collaboration UI selects the existing parameters and distinguishes saved scope from a new draft; historical questions exclude current-code hints, and metadata errors never trigger a default-scope paid fallback. No migration or default-mode change. See [ADR 0068](../docs/adr/0068-explicit-workflow-scope.md).

Coordinated runs now commit content-free events and model/tool/embedding reservations before callbacks, renew active ownership and save validated step results (ADR 0067). GET can observe progress while a synchronous POST waits. A failed later step retains earlier results; progress persistence refuses pending business writes and stops future calls if it cannot save. Same-UUID replay is still read-only; a process crash does not authorize automatic paid continuation. No migration is required; head remains `20261029_0019`. See [durability and limitations](../docs/adr/0067-durable-agent-progress.md).

BM25/source-aware BM25 now use `mixed-bm25-v2` / `mixed-bm25-source-v2`: keyset batches of 200, up to 50,000 scoped visible entities, global corpus statistics and per-entity ranking evidence budgets (32 quotes, 2000 characters each, 4000 ranking-text characters). `lexical.matched_count` and `results_truncated` distinguish Top K output from omitted scan/text; RRF uses the same lexical leg. No providers, schema migration, persistent index or formal graph writes are introduced. See [ADR 0066](../docs/adr/0066-batched-global-lexical-retrieval.md). Historical experiment scores are not v2 measurements.

`GET /sources/{id}/analysis-contexts` lists saved commits/duplicate local versions without providers. Explicit call analysis accepts snapshot_id or repeated version_ids and returns actual context; all strategies use immutable paths, bounded bodies and user/project/repository scope. Alias limits are checked after normalization, with merge-chain/unmerge retrieval regressions. Readiness checks physical0019 schema and critical tables/columns.

Index planning reads original-owner evidence in batches500 without changing hashes or paid-operation rules. Reproduce: `python -m scripts.benchmark_scale --output ../output/scale-new-run.json --repeats 20`; disposable native schema, no providers. See [API fields](../docs/API_CONTRACT.md) and [measurement scope](../evaluation/performance/2026-10-29-scale/README.md).

## Implemented behavior

- Liveness and PostgreSQL readiness endpoints.
- Request IDs, CORS, request logging, and a stable error envelope.
- Create, list, and retrieve projects within a development-user boundary.
- Resolve/list project-scoped local-folder identities, normalize GitHub HTTPS/SSH remotes, persist provider IDs and commit snapshots, optionally link remotes to local repositories, explicitly import bounded incremental GitHub Markdown/Java snapshots, and import versioned Issue/Pull Request plus Pull Request review-activity Markdown sources within the same user/project boundary.
- Validate and store UTF-8 Markdown and Java source with a SHA-256 content hash, optional repository identity, and normalized repository-relative path.
- Create/query parsing tasks and explicitly run them through the API.
- Automatically consume queued parsing tasks in an optional independent worker process, with leased claims, interrupted-task recovery, and fenced result writes.
- Persist Markdown headings/paragraphs/lists/fenced code and Java code/comment/type/method chunks with exact text, structure paths, hashes, and one-based inclusive line ranges. Top-level type annotations stay with the type; comment-only lines outside methods are separate comment chunks.
- Reuse the original source/task on identical-byte uploads within a user's project, nullable repository, and source type, even if the filename changes.
- Paginate stored chunks and safely repeat completed tasks or retry failed tasks.
- Derive a bounded read-only Java outline with stable type/field/method symbols, unqualified or `this.` same-file call hints, repository-scoped cross-file `extends`/`implements` targets, and method calls through explicitly typed direct type, field, parameter, and method-local receivers; derived structure is not promoted into the formal graph.
- Explicitly run one bounded Agent step over Java, Python, JavaScript/JSX, TypeScript/TSX, Go, C/C++, or C# call sites and same-repository declaration candidates. Candidate IDs and exact source-line evidence are server validated; empty candidate sets skip the provider and all results remain non-persistent.
- Persist project, source, task, and candidate-knowledge records.
- Promote confirmed candidates into scoped PostgreSQL entities, relationships, and evidence within the review transaction, with stable UUIDs, endpoint promotion, idempotent repeats, and legacy-confirmation replay.
- Serve read-only project graph, entity-detail, and relationship-detail views with user/project/time scoping, node/edge limits, and server-calculated evidence lines.
- Derive commit-pinned GitHub file URLs for imported sources and exact-line URLs for formal graph/search/question evidence while retaining provider-independent `project://` locators.

Explicit DeepSeek extraction, review, formal graph promotion, project keyword/vector/one-hop graph hybrid retrieval, and synchronous evidence-grounded questions are implemented. The semantic index uses an explicit rebuild operation and a configurable OpenAI-compatible Embeddings service. A real-provider/native-pgvector search smoke has passed; representative graph-bearing retrieval and real answer quality remain outstanding. Entity disambiguation, persistent history, and multi-turn Agent behavior are not implemented.

## Setup

### Reviewed evolution and native acceptance

Apply head `20261029_0019` before using the time/evolution/governance panels. Cross-source proposals are separate from extraction candidates; only human confirmation can close the old interval and start the new one. History retains evidence, governance is read-only, and dates cannot precede promotion or be scheduled in the future. See [ADR 0039](../docs/adr/0039-reviewed-knowledge-evolution.md).

From `backend/`, run `.\.venv\Scripts\python.exe -m scripts.verify_native` for disposable-schema migration/API/contention/Worker checks. Requires configured native PostgreSQL, pgvector already in `public`, and `CREATE SCHEMA` permission. It explicitly qualifies the Alembic version schema, verifies local tables before tests and removes only its generated schema. Existing business data is not test data. `--github` additionally permits real read-only public petclinic import/search/repeat/commit-provenance acceptance; it never calls models or uses a GitHub token. Ordinary `pytest` skips these opt-in checks. Model/embedding quality and private-token acceptance are not covered.

`GITHUB_IMPORT_MAX_FILES` sets the per-batch file budget (1–50, default 50). Whole-repository sync follows saved continuation snapshots at a fixed commit. Anonymous public GitHub file reads use commit-pinned raw content with Git blob hash validation. Use the parsing Worker to consume queued files during import. GitHub rate limits can pause sync, and saved batches can be resumed.

```bash
python -m venv .venv
# Activate the virtual environment for the current shell.
python -m pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and set `DATABASE_URL` to your native local service settings. The example credentials are development placeholders, not your existing database credentials. API and worker must use the same environment file from `backend/`.

Start your locally installed PostgreSQL, and create a dedicated `knowledge_atlas` database (or configure another database name). PostgreSQL must have pgvector installed: the initial migration runs `CREATE EXTENSION IF NOT EXISTS vector`, so the account needs permission or an administrator must enable it in the target database first. Docker is not required.

Then apply the schema and start the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

OpenAPI documentation is available at `http://localhost:8000/docs`.

## Exercise the parsing flow

Use the interactive API documentation in this order:

1. `POST /api/v1/projects` to create a project.
2. For a folder, call `POST /api/v1/projects/{project_id}/repositories/resolve` with its root name, then upload each supported UTF-8 Markdown/code file through `POST /api/v1/projects/{project_id}/sources` with `repository_id` and a normalized repository-relative `relative_path`. Single-file uploads omit both fields. Optionally register a GitHub HTTPS/SSH remote through `POST /api/v1/projects/{project_id}/repositories/resolve-github`, then explicitly call `POST /api/v1/projects/{project_id}/repositories/{repository_id}/sync-github` for a bounded file snapshot or `POST /api/v1/projects/{project_id}/repositories/{repository_id}/import-github-work-items` for recent Issue/Pull Request versions.
3. `POST /api/v1/tasks/{task_id}/run` to synchronously execute parsing.
4. `GET /api/v1/tasks/{task_id}` to inspect status and error information.
5. `GET /api/v1/sources/{source_id}/chunks?page=1&page_size=20` to inspect evidence text and line locations.

`GET /api/v1/projects/{project_id}/sources` restores the source list and each source's latest task after a frontend refresh. It includes nullable repository ID/name, `relative_path`, and commit-pinned `git_url` metadata but excludes original content; use the source-detail endpoint for preview text. Local sources return a null Git URL. Identical-byte reuse retains the first source's filename and relative path within the same nullable repository.

Markdown tasks use `markdown_parsing`, Java tasks use `code_parsing`, and legacy queued `knowledge_extraction` uploads can run Markdown parsing only. Successful tasks end at `succeeded`/`parsed`/100 and sources become `ready`. This does not mean knowledge extraction has run. Execution failures return HTTP 200 with a `failed` task and a sanitized error; the same endpoint retries failed tasks. Repeating a succeeded task returns the existing result, while running/cancelled tasks return HTTP 409. Re-upload responses contain the reused task's current status, which need not be `queued`.

The Markdown parser supports ATX/Setext headings, paragraphs, lists, and fenced code.

The Java static-import extension resolves unqualified calls through explicit `import static Type.method` and on-demand `Type.*` imports to accessible static methods in other ready sources within the same repository. Existing member names conservatively block import fallback even when their arity does not match; explicit imports block wildcard fallback. Cross-file responses use `receiver="import static"`, retaining original method IDs/lines, ambiguity, and existing bounds. Qualified `this`/`super` calls never use imports. This is a bounded extension, not complete Java access/overload resolution; see [ADR 0030](../docs/adr/0030-java-static-import-calls.md).

Java structure/call analysis V1 is read-only and repository-scoped (100 ready sources, 20 MiB of related text). It derives stable type/field/method symbols, same-file calls, inheritance targets, and cross-file method candidates. Lexical scopes include ordinary/if/else/while/try/catch/finally, braced enhanced/classic for, and resource try bodies. Header calls are omitted; header bindings end with the body. Unknown `var`, array elements, and multi-catch parameters shadow rather than guess. A complete method-local `var value = Type.factory(...)` can use one agreed, accessible repository-local static-factory return type after argument-count filtering. See [ADR 0036](../docs/adr/0036-bounded-java-static-factory-var-receivers.md) and the unqualified-call extension below.

Factory inference also accepts complete unqualified `factory(...)` initializers through current/inherited static members or explicit/wildcard static imports. Member names take precedence, including arity mismatches; private static members are accepted only in the exact current type through unqualified calls. Missing selected import owners, incomplete member lookup, non-static/unknown/conflicting returns, shadowed type qualifiers and method type-parameter returns keep locals unknown. Chained, instance and `this`/`super`-qualified factories remain outside this slice. See [ADR 0037](../docs/adr/0037-unqualified-java-factory-receivers.md) and `tests/test_java_factory_receivers.py`.

The same factory rules apply to `var` in braced classic-for single declarations and resource-try single/multiple declarations. Header and body declarations are processed in source order, including resource-name shadowing from earlier to later initializers. Bindings last only through the body and nested scopes, ending before catch/finally or siblings; header call edges remain omitted. Unknown initializers still shadow rather than fall back. See [ADR 0038](../docs/adr/0038-java-header-factory-receivers.md) and `tests/test_java_header_factories.py`.

Method candidates are filtered by argument count, including varargs. Unknown expression arity preserves candidates. Bounded inheritance lookup deduplicates diamonds and suppresses matching inherited signatures, but keeps same-arity type overloads and duplicate source versions ambiguous. Inherited unqualified/`this`/`super` calls link to original method symbols. Private methods, constructors, and interface static methods are not inherited; cycles or the 256-visit lookup budget report truncation. No runtime dispatch, full access/type checking, general factory/chained inference, reassignment data flow, or external classpath solving is claimed. See [V1 capabilities and acceptance](../docs/JAVA_ANALYSIS_V1.md).

Array fields/parameters/locals and varargs parameters remain bound as unknown receivers, suppressing element-method guesses and same-name field/type fallback. Both bracket positions and multidimensional arrays are covered; scalar generic receivers containing array type arguments remain scalar. Factory return types retain their resolved identity across caller imports, including unnamed-package types and duplicate versions. See `tests/test_java_receiver_safety.py` for parser and API regression coverage.

Chunk IDs remain stable for the same source and boundaries. Changed bytes create a separate source rather than updating an existing source. PostgreSQL project locks serialize repository resolution and duplicate upload creation; SQLite does not validate those locking guarantees. The manual endpoint runs parsing in the API process; automatic execution uses the worker described below. A GitHub sync reads one explicit snapshot, imports at most 50 supported files with a 20 MiB aggregate budget, persists commit/file provenance, and reuses unchanged blobs from the preceding snapshot. Complete trees report renames and deletions; deleted remote files remain immutable historical sources and resolve to their last non-deleted commit link. A separate explicit action imports at most 20 recently updated Issues/Pull Requests and 20 issue comments per item. For each selected PR it also imports an independent content-digest snapshot containing at most 20 reviews and 20 inline review comments. With a configured token, the snapshot additionally includes at most 20 GraphQL Review threads and 20 comment identifiers per thread, including current resolution state and resolver. Without a token REST import still succeeds and reports the missing enrichment. Exact resolution event time, attachments, reactions, full pagination, webhooks, polling, and source/knowledge invalidation are not implemented.

GitHub synchronization retries incomplete same-commit snapshots when the existing Sync action is used again. Completed sources/tasks are reused only within the same user/project/repository and source type, with compatible parsing tasks. Tree/file/byte truncation, size skips, or missing/incompatible source/task links trigger a fresh bounded snapshot; successful old snapshots remain unchanged. Complete snapshots (including deterministic empty/encoding/path skips) still short-circuit. A 50-file cap remains a selection cap, not pagination; repeated attempts cannot guarantee full repository import. Incomplete tree/file selections do not imply renames. Markdown/Java extension changes create or reuse the correct typed source rather than rename an incompatible one. See [ADR 0031](../docs/adr/0031-recoverable-typed-github-snapshots.md).

`GET /api/v1/projects/{project_id}/sources/{source_id}/chunks/{chunk_id}` reads one exact persisted chunk in a non-archived, user/project/source-scoped context. It returns the existing chunk shape, including zero-based `position`, without requiring a parsing task or scanning all chunk pages. Missing/mismatched records return 404 `SOURCE_CHUNK_NOT_FOUND`; inaccessible projects retain their project 404. This supports local graph/search/answer evidence navigation without migration or provider calls. See [ADR 0035](../docs/adr/0035-exact-evidence-source-navigation.md).

### Code symbol lookup

`GET /api/v1/projects/{project_id}/code-symbols?q=save&kind=method` searches ready Java sources without invoking a model or writing knowledge. Optional `repository_id` narrows the project scope; `limit` defaults to 50 (1–100). Matching is a case-insensitive literal substring of the local outline qualified name or source path. At most 100 sources, 20 MiB of text and 200 symbols per source are scanned; oldest sources are considered first. `scanned_source_count`, `matched_count` and `truncated` describe the bounded scan, not a global count. Hits retain outline IDs/lines, source/repository/task metadata, nullable `chunk_id`/zero-based `chunk_position`, and commit/line-pinned `git_url`. No pagination beyond these bounds or compiler resolution is implied. See [ADR 0032](../docs/adr/0032-bounded-code-symbol-search.md).

### Saved commit evidence

`GET /api/v1/projects/{project_id}/repositories/{repository_id}/snapshots` lists saved metadata with nullable `commit_source_id` / `commit_task_id`. `POST` to the same path plus `/{snapshot_id}/commit-source` (no body) returns HTTP 200 with `snapshot_id`, `source_id`, `task_id`, current `status`, `reused`, and canonical `git_url`. It renders saved SHA, UTC timestamp and commit message as deterministic Markdown, reusing repository-scoped ingestion. It performs no GitHub/model request and does not start parsing/extraction. Same bytes across refs/renames reuse the source; different repositories do not. Size limits and normal 404 scope rules apply; invalid SHA returns 409 `SNAPSHOT_COMMIT_INVALID`. Commit evidence opens `/commit/{sha}` without `#L` fragments: local lines refer only to the saved Markdown, not the patch. Apply migration `20261022_0014` first. See [ADR 0033](../docs/adr/0033-saved-commit-evidence-sources.md).

Saved file provenance is available at `GET /api/v1/projects/{project_id}/repositories/{repository_id}/snapshots/{snapshot_id}/files?page=1&page_size=20` (1–100 per page). It reads persisted rows only, sorted by path/UUID, including deleted and skipped records; `total` is a record count, not complete repository coverage. Source/task links are nullable and scope/type checked without loading source bodies. File URLs use the selected commit and current normalized remote coordinates; deleted paths have no URL into that commit, while retained local sources remain openable. No migration or provider request is needed beyond the existing snapshot schema `20261022_0014`. See [ADR 0034](../docs/adr/0034-snapshot-file-provenance.md).

## Automatic parsing worker

Apply the latest migration first. In another terminal with the backend virtual environment activated, run:

```bash
python -m app.worker
```

The worker polls queued tasks and expired running tasks within the development user's active projects. It shares the parser and persistence workflow with the API. Upload responses remain HTTP 202 with task IDs; refresh task/source state in the UI to view the result. No browser polling or automatic retry of ordinary failed tasks is added.

For a single pass:

```bash
python -m app.worker --once
```

`--once` handles at most one task. Exit code 0 means a task succeeded or no work was available; 1 means processing, recovery-limit handling, or an infrastructure operation failed. `--user-id <uuid>` explicitly scopes the trusted local worker to another user; the default is the same temporary development UUID as the API.

| Environment variable | Default | Behavior |
| --- | --- | --- |
| `TASK_LEASE_SECONDS` | `300` | Fixed execution lease, 1–86400 seconds; use the same value for API and worker |
| `TASK_MAX_ATTEMPTS` | `3` | Recovery stops an expired task at this total attempt count, 1–100 |
| `WORKER_POLL_INTERVAL_SECONDS` | `2` | Wait between idle/error iterations, greater than 0 and at most 60 |

Each claim gets a fresh internal execution UUID, an incremented attempt count, and an expiry time. If a process is killed, another worker can claim the task after expiry. Legacy running tasks without a lease use their start time (or last update time when absent) as the timeout baseline. Reaching the attempt limit marks the task/source failed with `TASK_ATTEMPTS_EXHAUSTED`; explicit manual retries remain possible beyond the count. Normal parsing failures stay failed for manual retry.

Both success and failure updates require the current execution UUID and running status. Chunks, source state, and final task state commit atomically. A replaced process cannot overwrite the current result even if it resumes later. Leases have no heartbeat: a live parser exceeding its lease can overlap a replacement in computation, so size the lease above normal parsing duration. SIGINT/SIGTERM request exit after the current iteration; forced termination relies on lease recovery.

Docker Compose is an optional alternative: from the repository root, `docker compose up -d --build` also starts the worker. It waits for the API's liveness check after migrations, uses the same backend image, and has no HTTP port. Default acceptance uses native local PostgreSQL; the user reports native PostgreSQL 17/pgvector startup, ingestion, duplicate reuse, restart persistence, and automatic parsing passed; PostgreSQL contention/recovery fault injection remains unverified. Optional container startup has not been verified.

## DeepSeek candidate extraction and review

Extraction protocol `knowledge-candidates-v2` allows date phrases quoted in a candidate's evidence. The server resolves supported relative expressions against the selected note revision in UTC. Reviewers can keep, change or clear the proposed validity interval before confirming. The existing graph columns store the reviewed interval, with an inclusive start and an exclusive end.

Apply `alembic upgrade head` (expected `20261029_0019`) before review or semantic-index operations. Configure only the backend `.env`:

```dotenv
DEEPSEEK_API_KEY=your_local_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_TIMEOUT_SECONDS=120
EXTRACTION_MAX_INPUT_CHARS=60000
EMBEDDING_API_KEY=your_embedding_key
EMBEDDING_BASE_URL=https://your-provider.example/v1
EMBEDDING_MODEL=your-1024-dimension-model
EMBEDDING_DIMENSIONS=1024
GITHUB_TOKEN=optional_read_only_token
GITHUB_API_BASE_URL=https://api.github.com
GITHUB_GRAPHQL_URL=https://api.github.com/graphql
GITHUB_API_VERSION=2026-03-10
GITHUB_TIMEOUT_SECONDS=30
```

The default model follows the [DeepSeek API documentation](https://api-docs.deepseek.com/). The adapter uses JSON output and non-thinking mode; schema validation still happens locally. `GITHUB_TOKEN` is optional for public REST imports; private repositories and GraphQL Review thread state need a backend-only token with the minimum Contents, Issues, and Pull requests read permissions used by the selected import. Empty or whitespace-only token values are treated as unconfigured. `GITHUB_GRAPHQL_URL` defaults to GitHub.com's endpoint and can be configured independently for compatible test endpoints; remote registration still supports GitHub.com only. Restart the API after configuration changes. The local environment file already has empty/default fields where absent; keep actual secrets out of Git and browser configuration.

After parsing a source, open its candidate section and explicitly request extraction. This sends that source's chunks to DeepSeek. `POST /api/v1/sources/{source_id}/extract` executes synchronously; `GET /api/v1/sources/{source_id}/extraction` reads task state. The parsing worker never initiates model calls. Limits are 100 chunks and 60000 characters in serialized input JSON by default, 50 entities, 100 relationships, 8192 output tokens, and a 1 MiB response. Oversized input is rejected, not silently truncated; split it into smaller sources.

Outputs must match the schema, reference only extracted entities, and quote exact text from same-source chunks. A whole batch is accepted or rejected. Successful extraction is reused per source/prompt version, including after model-setting changes; this version has no forced re-extraction. Failed calls require explicit retry. Interrupted calls can be retried after their lease expires (at least the configured task lease or model timeout plus 60 seconds); stale executions cannot overwrite a replacement. No automatic retry is made because it could repeat model charges. A timed-out/interrupted call may already have reached the provider.

Review candidates through `GET /api/v1/projects/{project_id}/reviews` and `POST /api/v1/reviews/{review_id}/resolve`. Confirm or reject, optionally editing name/summary before confirmation. Relationships require confirmed endpoint entities. Repeating the same decision is idempotent; changed decisions, merge, undo, and re-extraction are not supported. Migration `0004` adds audit records with actor, time, and before/after values. Migration `0005` adds formal graph tables; downgrading it removes graph records and evidence while preserving sources, candidates, and review events.

Confirmation writes formal entities, relationships, and evidence in the review transaction. Semantic vectors are generated later by an explicit index operation and cannot fail confirmation. Entity merging and disambiguation remain future work; real DeepSeek answer quality and embedding providers require separate acceptance.

## Project graph

`GET /api/v1/projects/{project_id}/graph` returns `nodes`, `edges`, and `truncated` for active, user-scoped projects. Optional parameters are `center_id`, `depth` (1 or 2), `types` (comma-separated entity types), `valid_at`, and `limit` (1–200, default 100); edges are capped at 500. Visibility requires non-archived status and a current or saved historical validity interval at the query time, followed by effective identity projection (ADR 0056).

`GET /api/v1/knowledge/entities/{entity_id}` returns the entity, up to 100 direct relationships, and evidence with the original filename, `project://` URI, nullable GitHub URL, quote, heading path, and server-calculated line range. Repository-file links are commit-pinned to exact lines; Issue/Pull Request links open the canonical conversation while line ranges refer to the imported Markdown snapshot. `GET /api/v1/knowledge/relationships/{relationship_id}` returns the relationship and its evidence. Canvas coordinates are not part of the API; layout belongs to the frontend.

Verification on 2026-10-17: 100 backend tests passed; the frontend build and desktop/mobile browser flows passed using isolated SQLite and simulated extraction. Native PostgreSQL 17.10 with pgvector passed migration upgrade/downgrade/re-upgrade, graph/evidence reads, and four concurrent identical confirmations per candidate using independent sessions in a disposable schema. The temporary schema was removed. The application schema was subsequently upgraded to `20261017_0005` to repair missing graph tables; live graph/review/source/search reads returned 200. Real DeepSeek quality, native-database browser acceptance, and Worker/API contention/recovery remain separate checks.

Verification on 2026-10-18: 102 backend tests, the frontend production build, and desktop/mobile real-page walkthrough passed. The application database completed `0005 → 0006 → 0005 → 0006`; pgvector `0.8.7`, the `vector(1024)` column, and cosine operations were confirmed. Tests use simulated embeddings; no embedding provider is configured in the current `.env`, so real semantic-recall quality remains unverified.

Later on 2026-10-18: the full suite reached 104 passing tests after hybrid retrieval was added. A configured real embedding provider and native PostgreSQL/pgvector returned seven indexed hybrid results in the browser, with visible component scores and evidence; that project had no confirmed relationships, so nonzero graph explanations remain covered by automated tests rather than this smoke dataset.

Final verification on 2026-10-18 reached 109 passing backend tests. Focused question tests cover supported answers, citation-boundary rejection, no-evidence refusal without an answer-model call, missing configuration, provider failures, and request validation. The frontend production build and desktop/390 px browser walkthrough passed; the visible answer used a browser-local intercepted response, so real DeepSeek answer quality remains unverified.

## Keyword, semantic-vector, and hybrid graph search

`GET /api/v1/projects/{project_id}/search` supports `mode=keyword`, `mode=vector`, and `mode=hybrid`. Keyword mode retains deterministic name/summary/evidence weighting. Vector mode embeds the query with the configured model and performs exact pgvector cosine-distance ranking over indexed formal entities. Hybrid mode uses fixed `0.3/0.4/0.3` keyword/vector/one-hop graph weights, bounded visible relationships, and returns normalized components plus relationship explanations. All modes support `types`, timezone-aware `valid_at`, and `top_k` and return up to three source evidence records.

Call `POST /api/v1/projects/{project_id}/embeddings/rebuild` before semantic, hybrid, or question requests. It sends formal entity type, name, summary, and evidence to the configured embedding service and writes `knowledge_embeddings`; unchanged model/content hashes are reused. This is separate from confirmation. Vectors are currently fixed at 1024 dimensions and no approximate index is created. See [ADR 0009](../docs/adr/0009-explicit-semantic-index.md) and [ADR 0010](../docs/adr/0010-explainable-hybrid-graph-retrieval.md).

## Evidence-grounded questions

`POST /api/v1/projects/{project_id}/questions` accepts a 1–200 character question and optional timezone-aware `valid_at`. It synchronously runs bounded hybrid retrieval, gives DeepSeek only the selected formal evidence, validates strict JSON and citation membership, and returns only cited evidence with entity and retrieval summaries. With no evidence it returns a deterministic unsupported answer without calling the answer model. Responses are not persisted; history, streaming, and multi-turn orchestration are deferred. See [ADR 0011](../docs/adr/0011-synchronous-evidence-grounded-questions.md).

## Test

```bash
python -m pytest
```

Tests use isolated SQLite databases and cover parsing, API behavior, failure/retry, access isolation, migration upgrade/downgrade with legacy running tasks, offline PostgreSQL SQL compilation, worker recovery/fencing across independent sessions, actual one-shot worker subprocesses, candidate review, formal graph promotion, legacy-confirmation replay, and bounded graph queries. Run `/api/v1/health/ready` against your configured native local services to verify the real PostgreSQL connection. The PostgreSQL dependency must report `up` for acceptance. Offline compilation is not a live database integration test.

## Structure

```text
app/
├─ worker.py     # Independent database-backed parsing consumer
├─ api/          # Versioned HTTP routes and dependencies
├─ core/         # Settings, errors, logging, and middleware
├─ db/           # SQLAlchemy base and session factory
├─ models/       # Authoritative persistence models
├─ schemas/      # API request and response models
└─ services/     # Persistence workflows and domain validation
migrations/      # Alembic environment and revisions
tests/           # API behavior tests
```

