# Changelog

[简体中文](CHANGELOG.zh-CN.md)

All notable changes to Knowledge Atlas will be documented in this file.

The project is pre-release. Version numbers and release dates will be added when the first distributable milestone is defined.

## Unreleased

- Sync whole GitHub repositories through commit-pinned batches, show progress, and retain the last successful checkpoint on interruption.

- Add a PostgreSQL/Neo4j switch, explicit snapshot sync, and snapshot time and totals to the graph page. Neo4j graph details and evidence are read at the snapshot time.

- Add optional Neo4j connectivity, explicit per-project formal graph snapshot sync, and scoped Cypher neighborhood queries. [ADR 0081](docs/adr/0081-neo4j-project-projection.md).

- M5 offline preparation: frozen independent20-task packet, zero-call scoped preflight, exact reported-run/grade binding, explicit ungraded/all-attempt denominators, transport-blocked repeatable acceptance and CI packet checks. No live execution or release certification. [Runbook](docs/PROJECT_ASSISTANT_M5.md).

- M3/M4: immutable notes/autosave/history/citations, editable report drafts, explicit capability-scoped import/parse/extract operations and version-bound human approvals for note edits and formal confirmation/merge/replacement/retirement. Migration0023 followed verified31-table backup/recovery and preserved30 old business-table fingerprints. No live calls; M5 remains planned. [Implementation](docs/PROJECT_ASSISTANT_M34.md).

- M2 adds202 async task submission, a separate runner, atomic attempted-call/checkpoint/artifact receipts, cancellation and explicit continuation with unknown-outcome acknowledgement. Preserve sync v1 and historical workflows. Business migration0021 followed verified backups/restores and old-table fingerprints; local full1036/12 skipped, coverage95.42%, native274, frontend143/build and desktop passed. No live providers or M3–M5 work. See [M2](docs/PROJECT_ASSISTANT_M2.md).

### Project assistant M1 (locally verified with substitutes)

- Added a unified read-only goal entry with scoped document, confirmed knowledge and code tools; typed exact references, clarification and durable read-only replay.
- Added separate assistant/tasks contracts and reversible migration `20261031_0020`, preserving legacy workflows. No live calls, auto migration, async runner or write tools; M2–M5 remain planned. See [M1 checks](docs/PROJECT_ASSISTANT_M1.md).

### Earlier unreleased changes

- Document the proposed whole-project Agent development plan in English and Chinese on `feat/project-agent`, covering tool scope, durable execution, artifacts, note revisions, approvals and M0–M5 acceptance. New capabilities remain planned; no runtime, migration or live-provider change.

- Fix GitHub CI portability: keep the PostgreSQL health command in one quoted argument, isolate mocked compiler failures from local TypeScript installation, and configure source-retrieval QA tests explicitly instead of depending on local credentials. Preserve coverage thresholds and production validation.

- New answers use `evidence-claims-v3`: the server derives aggregate support from claims; strict citations and saved v2/flat history stay compatible. Add independent synthetic development regressions for both provider paths and explicit versioned diagnostics (ADR0075). No live calls or v3 quality claims; historical failures, scores and ledgers stay unchanged.

- Complete the explicitly authorized457-request CF Clef holdout judgment, preserving91 graded/96 total and5 invalid-output exclusions. Add offline fingerprint-checked summaries, confidence/uncertainty/denominator reporting, figures and a thesis/demo draft.83 correct labels are model-only;80/183 citations uncertain and all abstention low-confidence. No changes to frozen inputs/prior ledgers or new answer/embedding calls.

- Repair opt-in evaluation: invalid outputs remain explicit case failures instead of aborting independent cases; production validation/other-error fail-stop stay strict. Add exact scoped diagnostic reuse, sanitized constraint codes and hashed judge exclusions (ADR0074). Retry96 records:91 valid/5 invalid, diagnostic1+main95 model/73 embedding requests. No prompt/ranking/gold changes; CF Clef preflight457, no new live judge calls.

- Add explicitly granted96/73 holdout round ledgers with immutable scope, atomic before-call reservations and one-output claims, preserving historical usage. The first live attempt stopped on invalid answer5, saved4 BM25 answers and consumed5/1; no automatic retry/judge. Archive partial artifacts and native cleanup proof. Subsequent errors retain sanitized exception/validation types and case IDs without inputs or response text.

- Add read-only historical answer diagnostics and a current online QA acceptance plan for frozen public-v2/holdout-v3. Preserve per-case historical time, claim/input-pool exports and a separate compatible numeric-scoring projection; gate live use on cumulative budgets and an exact reviewed preflight. Historical Clef80-answer/214-request analysis is separate from current-system quality. New real calls0; human grading0%.

- Add OpenRouter Jev Decisions API for offline anonymous grading, with separate credentials, explicit provider authorization, proxy support, strict release/dated-snapshot validation and fail-stop on model drift. Preserve actual token usage/optional cost and old providers; no live requests this turn (ADR0073).

- Add explicit Cloudflare Workers AI offline judging: native REST, Clef decision format and configurable text-model JSON Schema labels. Preserve Jev commands, anonymity, attempt reservations and zero-call preflight; record provider/model/configuration and missing chat confidence without fabricated probabilities. No live calls or business-provider changes (ADR0072).

- Add bounded symbol metadata reuse, opt-in lightweight collaboration history with on-demand full details, versioned native lexical-v2/cache/payload measurements and extracted workflow/parser modules. Add offline Jev-only anonymous grading with an explicit call cap and zero-call preflight; human coverage remains0%, no live Jev calls this turn.

- Collaboration history now batches task review counts: a 50-task page with candidate IDs uses 4 SELECTs instead of 153, preserving pagination, exact review subsets, saved scope and read-only expiry. Candidate-free pages use 3 reads; no provider calls or schema changes.

- Claim-level answers are implemented in [ADR 0069](docs/adr/0069-answer-claim-evidence.md): `evidence-claims-v2` binds each supported claim to current scoped evidence, marks insufficient claims separately and supports exact source navigation. The server derives legacy flat fields; old records remain readable without inferred attribution or new provider calls. Structural validation does not establish semantic entailment. Frozen experiments, the 84/61 provider ledger and schema head `20261029_0019` remain unchanged; human grading is deferred.

- Collaboration tasks expose retrieval mode, optional local knowledge time and fixed-commit/local code-version choices with a draft scope preview. History excludes current code; failed/loading metadata blocks submission and retries reads only. Saved tasks return an allowlisted scope for refresh/review without exposing raw requests or replaying calls. Defaults/schema remain unchanged (ADR 0068).

- Collaboration runs persist events and call reservations before callbacks, renew fenced ownership and save validated code/extraction/answer checkpoints. Earlier results remain readable after later failures or interruptions; progress storage failures stop subsequent calls, pending business writes are never auto-flushed, and checkpoint labels are localized. No schema change or automatic paid replay (ADR 0067).

- BM25 and source-aware BM25 scan scoped knowledge in bounded batches with global statistics, covering matches beyond the former 1000-entity window up to an explicit 50,000-entity budget. Each entity has an independent ranking evidence budget; v2 metadata separates matched counts and Top K truncation from omitted scan/text. RRF uses the same lexical path; historical experiments remain unchanged (ADR 0066).

- Removed unused frontend bindings and backend imports; cleaned local build/test caches and one-off diagnostics while preserving dependency environments, database backups, provider budgets, grading files and experiment records. Ignore coverage shards/reports to keep generated files out of commits.

- Single-project code/extraction/evidence agents with bounded LangGraph tools and shared budgets; saved collaboration tasks, explicit human review/resume, source/evidence navigation and read-before-resend. Migration0019; legacy interfaces remain compatible. Provider quality and human grading are separate acceptance (ADR0064–0065).

### Added

- Schema/version-aware readiness; fixed-commit and explicit local-version code analysis; normalized identity regressions; restorable URLs and graph task sections; a separate genuine public-document holdout-v3; native 1k/10k measurements and batched index evidence. Current documentation is separated from historical checkpoints; real blind grading is deferred by the user (ADR 0060–0063).

- Audited identity aliases/merge/unmerge and lifecycle reactivation/reversal with preserved temporal intervals; atomic split/merge replacements. Persistent grounded conversations, real workbench/navigation and contextual search; resumable pinned GitHub manifests. Explicit Java/TypeScript/Go static compiler paths. Separate public-v2 online experiment and offline blind review; question default RRF, human/private acceptance pending (ADR 0056–0059).

- Projected source pagination/latest tasks and batched search evidence with native measurements; explicit reasoned knowledge retirement with audit/history; scoped import/review/graph orchestration modules (ADR 0053–0055).

- Persisted server-side index rebuild ownership, refresh recovery and explicit interrupted retry, with uncertain-result transport errors and bounded model request budgets.
- Optional source-aware BM25 plus new regression/diagnostic artifacts; verified PostgreSQL snapshot backup and guarded fresh-target recovery tools.

- Source filename/path, language and parsing-state filters apply before pagination; filtering preserves the opened original source and explains when it is absent from the current results. Failed source pages retry their requested page, and disappeared pages recover to the last valid page.

- Relation review cards display scoped endpoint names/statuses across filtering and pagination, with entity-list navigation and named batch dependency explanations before final confirmation.

- Search/index lifecycle and App integration regressions cover context round trips, retries and clearing during rebuild. Search state is now isolated in a tested composable.

- Server-side candidate status/kind/text filtering with page recovery and selection invalidation. Governance filters categories before result limits and reports bounded-scan counts.
- Read-only two-entity evidence comparison with project/ID validation and late-response protection. Deduplicated question evidence retains related entity navigation and model context.


- Explicit selected-candidate batch review with a named preview, entity-first atomic promotion, audit idempotency and all-or-nothing rollback. Review requests lock project/source/navigation context.
- Provider-free index inspection reports missing rows and stale canonical content hashes with effective-time isolation and a 1000-entity inspection limit; successful rebuild refreshes the status.


- Optional BM25/vector RRF search and selectable question retrieval; online evidence deduplication and fair per-entity allocation, with visible budget counts. Existing search defaults and historical baselines remain unchanged.
- Source-wide live review progress and next steps; duplicate detection within all same-name summary groups, prioritized findings and direct evidence-review navigation.
- Shared latest-request state and App-level clear/project-switch/retry regressions. No new model-quality claim; merges and undo remain unimplemented.

- Bounded provider-free BM25 Chinese/English search with terms, scope-aware corpus statistics, scan limits and UI explanations; a separate 40-question development diagnostic preserves failures and old baselines (ADR 0044).
- Semantic queries skip embedding requests for empty matching indexes while preserving configuration errors; search forms now guard busy submissions. Added lexical/native regressions and three component cases (18 frontend tests total).

- Optional bounded read-only tool Agent with validated function arguments, scoped source snapshots, execution traces and the compatible single-step default; ten-language, 50-case call gold set.
- Approved real synthetic DeepSeek acceptance (112 requests), frozen-evidence answers, usage records, human blind-review packet/import and five reproducible scientific figures. Human semantic grades remain pending.
- Fifteen Vue/API regression tests, coverage reporting, CI jobs, a native Windows demo launcher and an optional full frontend/API/Worker/pgvector Compose stack. Docker builds and hosted CI remain unverified locally.

- Reproducible synthetic evaluation-project preparation through ordinary ingestion, parsing, audited confirmation and temporal review, with explicit annotation acceptance, new-project guards, all-or-nothing transactions and dataset/fixture/actual-graph fingerprints. Three-baseline orchestration explicitly builds embeddings, records provider attempts and per-hit graph diagnostics, and writes comparison tables without invoking an answer model. Dataset 1.0.1 fixes future evidence in a historical case; scoring protocol line-evidence-v2 accommodates formal quote trimming. See ADR 0042.

- Explicit bounded Agent-assisted cross-file call analysis for Java, Python, JavaScript/JSX, TypeScript/TSX, Go, C/C++, and C#. The backend extracts same-repository call/declaration candidates, accepts only candidate IDs in strict model output, returns exact source-line evidence, skips the provider when no candidate exists, and never persists or promotes derived edges; the desktop workspace exposes loading, empty, error, retry, syntax-warning, and truncation states. See ADR 0041.
- A frozen Stage 6 V1 evaluation set with 30 synthetic document/code/Git sources and 40 stratified Chinese questions covering direct facts, cross-document reasoning, code location, temporal history, and grounded refusal. Line-exact gold evidence, answers, schemas, fingerprints, deterministic validation, prediction scoring, manual grading coverage, and bilingual experiment instructions are included; no provider call or real-quality claim is made.
- A guarded experiment runner for keyword, vector, and hybrid modes. It requires an exact isolated corpus snapshot, complete vector coverage, explicit provider authorization, and corpus-bounded evidence; it writes non-overwriting run manifests, complete or partial predictions, immediate metrics, latency, and provider-call counts without secrets or raw provider responses.

- Multi-language upload/folder/GitHub/Worker parsing for Python, JavaScript/JSX, TypeScript/TSX, Go, C, C++ and C#: lossless bounded chunks, deterministic outlines/search, language badges and syntax warnings. Optional GitHub `rescan` discovers new extensions in old complete snapshots while reusing blobs. Java analysis and review authority stay unchanged; see ADR 0040.

- Configurable GitHub scan file budget (`GITHUB_IMPORT_MAX_FILES`, 1–50, default unchanged at 50), with explicit truncation and same-commit recovery when increased, reducing anonymous-request pressure without requiring a token.

- Explicit cross-source replacement/supplement/conflict proposals and human review, with stable request UUIDs, revalidated formal evidence, atomic interval updates, immutable audit snapshots, historical graph/search navigation and a bounded evidence-linked replacement chain. Read-only governance flags missing evidence, same-name duplicates/possible conflicts and orphan knowledge without automatic writes; see ADR 0039.
- Reproducible 40-file repository API integration and disposable native PostgreSQL acceptance, including migration round trips, upload/review contention and Worker recovery fencing. Native isolation explicitly qualifies the Alembic version schema and validates local tables before tests.

- Static factory `var` receivers in braced classic-for and resource-try headers, reusing method-body candidate and agreed-return rules. Source-order/resource-order binding preserves earlier-name shadowing, excludes later-name retroactive shadowing, and confines receivers to the body and nested scopes. Header call edges remain omitted; unknown factories, duplicate versions and incomplete lookup retain conservative behavior. No API shape or migration changes.

- Java factory-local `var` inference now covers unqualified current/inherited static members and explicit/wildcard static imports, including private static factories in the exact current type. Member-name precedence, arity/varargs filtering, agreed return types, lexical lifetimes, original method IDs/lines, repository isolation and ambiguity are preserved. Shadowed type qualifiers, method type-parameter returns, missing selected import owners and mixed instance/static member candidates keep locals unknown. Focused coverage includes an upload/parse/structure API flow.

- Bounded Java method-local `var` inference for complete type-qualified static factory initializers when accessible repository-local candidates agree on one resolvable return qualified name. Later receiver calls retain original target symbols, lexical shadowing, argument-count filtering and ambiguity; unsupported, external, non-static, private or disagreeing factories remain unknown. No API shape, persistence or formal-graph write changes.

- Exact original-source navigation from graph entity/relationship evidence, knowledge search hits and answer citations, using a project-scoped chunk UUID lookup, original chunk pagination, keyboard focus/highlight, visible error/retry/cancel and stale-request fencing. No text/name guessing, migration, provider call or knowledge write is introduced.

- Read-only saved-snapshot file provenance with stable pagination, import/reuse/unchanged/rename/delete/skip states, original paths, blob IDs and skip reasons, scoped source/task links, selected-commit GitHub URLs, and desktop original-source navigation. Deleted files retain local sources without fabricated links into the deletion commit; missing/incompatible references remain unavailable. No new migration, provider request, patch or formal knowledge is introduced.

- Saved GitHub snapshot history in the desktop workspace and explicit commit-message Markdown import/open, scoped source/task reuse across refs and repository renames, canonical commit evidence links without fabricated line fragments, and a reversible nullable-link migration. No provider/model call, patch import, automatic extraction, or formal Commit entity is introduced.

- Bounded read-only Java symbol search in the source workspace, with literal case-insensitive name/path matching, repository/kind filters, explicit scan/result limits, original outline IDs/lines, source-chunk page navigation and focus, immutable GitHub line links, and empty/error/retry/clear states. Project, condition and navigation changes invalidate stale requests.

- Repository-local Java static-import method links for explicit and wildcard imports, with member-name precedence, accessible static candidates, arity/varargs filtering, stable original symbols, preserved ambiguity, and readiness/repository isolation. No compiler, migration, or formal-graph write is introduced.
- Integrated repository-local Java analysis V1 with braced classic-for/resource scopes, inherited method candidates and original symbols, override/diamond/cycle handling, conservative arity/varargs filtering, and combined acceptance coverage.
- Java cross-file calls within plain try/finally and explicitly typed catch bodies, with catch-parameter lifetimes, sibling isolation, unknown multi-catch shadowing, and outer-binding restoration.
- Java cross-file method links through explicitly typed enhanced-for elements in braced bodies, with nested/sibling scope isolation, outer-binding restoration, and conservative unknown `var`/array shadowing.
- Scoped Java local receiver links in ordinary/if/else/while brace blocks, with declaration lifetimes, sibling isolation, outer-binding restoration, and conservative exclusion of unsupported execution scopes.
- Repository-local Java method links through direct `var` locals initialized by a complete constructor expression, including qualified/generic types, exact lines, stable IDs, and conservative shadowing for unsupported initializers.
- Bounded GraphQL Pull Request Review thread-state enrichment with current resolved state, resolver, location, outdated state, bounded comment membership, token-aware REST fallback, immutable digest versioning, a reversible migration, and desktop counts.
- Explicit bounded Pull Request review-activity snapshots with up to 20 reviews and 20 inline review comments per PR, reply links, independent content-digest versioning, canonical PR links, truncation reporting, a reversible migration, and desktop summaries.
- Bounded Java cross-file call resolution for explicitly typed method parameters and direct method-body local variables, with conservative local/parameter/field shadowing, declaration-order checks, existing package/import resolution, and unchanged formal-graph boundaries.
- Explicit bounded GitHub Issue/Pull Request import with up to 20 recently updated items and 20 issue comments per item, deterministic Markdown sources, provider-ID/`updated_at` version reuse, immutable local history, canonical conversation links, existing parsing/review reuse, a reversible migration, and desktop controls.
- Immutable GitHub source and evidence links derived from persisted snapshots: source views open commit-pinned files, formal graph/search/question citations open exact line fragments, local sources return null, and remotely deleted files retain their last-existing snapshot link without a migration.
- Persistent GitHub commit/tree snapshots and per-file blob provenance, with same-commit short-circuiting, incremental unchanged/known-blob reuse, conservative rename/deletion records, provider-ID-backed repository coordinate updates, a scoped snapshot-history API, and expanded desktop synchronization summaries. Remote deletions remain non-destructive.
- Explicit bounded GitHub snapshot synchronization from a repository default branch or requested ref, with optional backend-only token authentication, deterministic selection of up to 50 Markdown/Java blobs, a 20 MiB aggregate budget, per-file import/reuse/skip results, existing parsing-task reuse, and desktop controls.
- Bounded repository-scoped Java cross-file method-call hints for direct type-qualified and current-type field receivers, with package/import resolution, stable target IDs, exact source paths and lines, overload ambiguity, truncation, and desktop outline presentation outside the formal graph.
- Normalized project-scoped GitHub remote registration for HTTPS, SCP-style SSH, and `ssh://` forms, with optional linking to local-folder repositories, remote-only identities, conflict isolation, a repository list UI, and a reversible migration. Registration does not contact GitHub or import repository content.
- Project-scoped local-folder repository identities with idempotent resolve/list APIs, nullable source membership, repository-relative paths, repository-aware duplicate reuse, repository labels in source views, and repository-bounded Java type resolution. Existing sources remain unassigned without backfill.
- Bounded repository-scoped Java type resolution in the source-structure view. Ready sources expose cross-file top-level `extends`/`implements` targets through explicit imports, same-package lookup, and wildcard imports, including target paths, source lines, ambiguity, and truncation without writing derived data to the formal graph.
- Separate desktop single-file and folder-upload entry points. Folder selection ignores unsupported/empty files, imports up to 50 Markdown/Java sources through the existing sequential upload contract, persists normalized relative paths, shows them in source/evidence views, and retains successful uploads when another file fails.
- A bounded read-only Java source-structure endpoint and desktop outline with stable type/field/method symbols, source lines, and same-file unqualified/`this.` call hints. Derived relationships remain separate from reviewed formal knowledge and report overload collisions as ambiguous.
- Bounded local Java source ingestion with `.java` upload validation, `code_parsing` tasks, leased-worker support, exact line-preserving `code`/`comment`/`type`/`method` chunks, stable structure paths/UUIDs, type-level annotation grouping, and desktop MD/JAVA source presentation. Complete ASTs, call graphs, GitHub import, and incremental repository sync remain out of scope.
- Synchronous, non-persistent evidence-grounded questions with bounded hybrid retrieval, strict DeepSeek JSON output, application-validated citation UUIDs, deterministic no-evidence refusal, retrieval summaries, and a responsive real frontend workspace with source-line and entity navigation.
- Explainable `hybrid` project search with fixed keyword/vector/one-hop graph weights, bounded visible-relationship expansion, normalized score components, relationship explanations, stable ranking, and frontend mode switching.
- Explicit formal-entity semantic indexing with a configurable OpenAI-compatible Embeddings service, 1024-dimensional pgvector storage, content-hash reuse, exact cosine retrieval, index coverage counts, and frontend keyword/vector mode switching.
- Evidence-backed project keyword search over confirmed entity names, summaries, and quotes, with deterministic ranking, type/time filters, literal wildcard handling, bounded results, and detail/neighborhood navigation. No migration or model call is required.

- Repository-local agent skills under `.agents/skills/` for extraction, review/promotion, migrations, verification, ingestion, frontend, and bilingual documentation workflows, indexed from `AGENTS.md`.
- Confirmation now promotes candidates into scoped PostgreSQL entities, relationships, and evidence in the same transaction as review state and audit events, including idempotent UUIDs, endpoint promotion, and legacy-confirmation replay. Read-only project graph and entity/relationship detail APIs expose time-filtered, bounded views without canvas coordinates.
- Explicit DeepSeek JSON candidate extraction with constrained types/endpoints, exact source-quote validation, atomic candidate persistence, reusable successful tasks, manual retry/expired-lease recovery, and fenced writes.
- Source-scoped candidate UI and paginated review APIs with confirm/reject, name/summary edits, endpoint confirmation rules, and reversible review-event migration. Model calls are not triggered by the parsing worker.

- Simplified Chinese companions for repository guidance, plans, contribution/security policies, changelog, backend/setup instructions, and ADR guidance/records, with reciprocal language links and a Chinese README index.
- Optional database-backed parsing worker with continuous/one-shot modes, scoped task polling, execution leases, stale-result fencing, interrupted-task recovery, and bounded automatic attempts.
- Reversible lease migration preserving historical tasks, shared development identity, worker configuration, and a Compose worker gated on API liveness after migrations.
- Worker tests for recovery, stale success/failure writes across independent sessions, boundary isolation, attempt limits, and actual one-shot subprocess success/failure.

- Interactive Vue 3 Mock knowledge-graph frontend.
- Node search, selection, evidence expansion, relationship navigation, type filtering, temporal playback, and Mock questioning.
- Responsive desktop and mobile layouts.
- Architecture, frontend, knowledge-model, API, and roadmap documentation.
- Repository instructions, contribution guidance, setup documentation, ADR process, and GitHub templates.
- FastAPI backend foundation with CORS, request IDs, health endpoints, and standardized errors.
- Project creation/list/detail, Markdown upload, source preview, and task-status endpoints.
- SQLAlchemy models and an Alembic migration for projects, sources, processing tasks, and candidate knowledge.
- Docker Compose services for PostgreSQL/pgvector and the API.
- Isolated backend API tests covering the first ingestion slice.
- Typed frontend API client functions while retaining Mock as the default data source.
- Explicit Markdown task execution, persistent heading/paragraph/list/code chunks, and paginated chunk APIs with stable UUIDs, exact text, heading paths, hashes, and source line locations.
- Identical-byte upload reuse within a user's project, idempotent completed tasks, failed-task retry, and atomic task claiming.
- Parsing/API regression tests, reversible chunk migration tests, and offline PostgreSQL migration compilation checks.
- API-backed frontend project/source workspace with project creation/pagination, Markdown upload, source preview, parsing/retry, chunk pagination, and loading/error/empty states.
- Paginated project-source listing with scoped latest-task references and interface tests.

### Fixed

- Java array fields, parameters and locals, including multidimensional/name-suffix declarations and varargs parameters, no longer generate calls to element-type methods or fall back to same-named fields/types. Scalar generic receivers containing array arguments still resolve normally, and lexical exit restores outer bindings.
- Factory-inferred Java return types retain their resolved source identity across caller imports. Unnamed-package types no longer get redirected to a same-named imported class; duplicate source versions retain ambiguity.

### Changed

- Clearing search keeps an outstanding index update busy, preventing duplicate rebuild requests in the same project. Project/time changes discard old completions; successful index updates retain BM25 results without rerunning lexical search.

- Explicit GitHub synchronization now retries incomplete same-commit snapshots, preserves successful typed source/task reuse, repairs missing or incompatible snapshot links, and avoids guessing renames from truncated file selections. Markdown/Java copies or extension changes cannot share the wrong parser task.

- Candidate review lists now place entities before relationships deterministically, preventing relation actions from appearing before their required endpoints.
- Removed the Neo4j driver, settings, readiness checks, and optional Compose service/volume declarations. PostgreSQL is the sole current database and stores the formal graph; Neo4j is deferred under ADR 0005. Readiness now reports only PostgreSQL and still returns HTTP 503 for a failed database connection.
- Native local PostgreSQL/pgvector are the default development and acceptance path; setup guides and plans now treat Docker Compose as optional and document actual local connection settings.
- Expanded the project README with current status, quick start, architecture, repository structure, and MVP definition.

### Known limitations

- The user reports PostgreSQL 17/pgvector startup, upload/parsing, duplicate reuse, restart persistence, and automatic parsing passed. PostgreSQL contention and lease-recovery fault injection remain unverified. Optional Docker startup has not been verified either.
- Worker leases are fixed without heartbeats or preemptive cancellation.
- Complete CommonMark parsing, entity disambiguation, retrieval-weight tuning, and multi-turn Agent behavior are not implemented. Real DeepSeek answer quality and representative native-pgvector hybrid quality with confirmed relationships remain unverified; automated tests cover nonzero graph fusion, while a seven-entity real-provider search smoke passed without relationships.
- The independent evidence-question workspace uses the real API, while demo-graph follow-up remains Mock. Question history, streaming, routing, and persisted view preferences are not implemented.
