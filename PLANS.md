# Knowledge Atlas Implementation Plan

[简体中文](PLANS.zh-CN.md)

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
- Optional database-backed parsing worker, leased execution, stale-result fencing, interrupted-task recovery, and bounded automatic attempts implemented.
- Explicit DeepSeek extraction with evidence validation, audited review, and promotion of confirmed candidates into scoped PostgreSQL entities, relationships, and evidence.
- Read-only project graph, entity-detail, and relationship-detail APIs with user/project/time scoping and node/edge limits, plus a real project-graph frontend page.
- Evidence-backed project keyword search over formal entity names, summaries, and quotes, with ranking, type/time filters, bounded results, and graph/detail navigation.
- Explicit 1024-dimensional formal-entity semantic indexing, pgvector cosine retrieval, content-hash reuse, and frontend keyword/vector mode switching.
- Explainable hybrid retrieval with fixed keyword/vector/one-hop graph weights, bounded candidates, visible-relationship filtering, and per-hit score composition.
- Synchronous evidence-grounded questions with bounded hybrid retrieval, strict DeepSeek output, application-validated citation UUIDs, and a real frontend workspace.
- Local UTF-8 Java source upload with deterministic `code`/`comment`/`type`/`method` chunks, exact source lines, and reuse of the existing parsing worker and evidence pipeline.
- Separate desktop single-file and folder-upload entry points; folders contribute up to 50 supported Markdown/Java files, uploaded sequentially with persisted relative paths, per-file deduplication, and partial-success retention.
- Bounded repository-scoped Java `extends`/`implements` resolution across ready sources using package and import rules, shown with target paths and lines outside the formal graph.
- Project-scoped local-folder repository identities, repository-relative paths, repository-aware duplicate reuse, and repository-bounded Java type resolution.
- Normalized project-scoped GitHub HTTPS/SSH remote identities, optional linking to an existing local-folder repository, remote-only registration, and a repository list UI. Registration performs no GitHub request or clone.
- Explicit bounded GitHub snapshot synchronization for the default branch or a requested ref, importing at most 50 Markdown/Java blobs with a 20 MiB aggregate budget through existing repository-scoped deduplication and parsing tasks.
- Persisted GitHub commit/tree snapshots with per-file blob provenance, same-commit short-circuiting, unchanged/known-blob reuse, conservative rename/deletion records, and provider-ID-backed repository rename handling.
- Derived immutable GitHub source/evidence URLs from persisted snapshots, with commit-pinned files, exact line fragments, local-source null fallback, and last-existing-snapshot behavior after remote deletion.
- Explicit bounded GitHub Issue/Pull Request import as deterministic Markdown, with up to 20 recent items and 20 issue comments per item, plus independent content-digest review snapshots containing up to 20 reviews, 20 inline review comments, and token-backed current state for 20 Review threads per selected PR, canonical conversation links, and desktop controls.
- Bounded repository-scoped Java method-call targets for explicitly typed direct type, current-type field, method-parameter, and direct method-local receivers, with conservative shadowing, target paths, exact lines, and ambiguity surfaced outside the formal graph.

- Explicitly typed and constructor-initialized `var` local receivers resolve within ordinary/if/else/while brace blocks, preserving declaration order, lexical lifetimes, sibling isolation, and conservative unknown shadowing; see [ADR 0025](docs/adr/0025-constructor-initialized-java-var-receivers.md) and [ADR 0026](docs/adr/0026-scoped-java-local-receivers.md).
- Braced enhanced-for bodies resolve explicitly typed element receivers; unknown `var`/array elements suppress fallback only within the loop body, and header calls remain omitted. See [ADR 0027](docs/adr/0027-enhanced-for-java-receivers.md).

## Active phase

The active phase is Stage 4 code ingestion. Its bounded local-file slice accepts Java files, uses `code_parsing`, preserves exact source lines in structural chunks, persists local-folder repository identities and repository-relative paths, and reuses the existing worker and evidence workflow. It resolves a small repository-local subset of cross-file type relationships and calls through explicitly typed direct type, field, method-parameter, and direct method-local receivers, registers normalized GitHub owner/repository coordinates, explicitly imports bounded default-branch or requested-ref snapshots, and imports recent Issue/Pull Request plus PR review-activity versions as Markdown. GitHub synchronization persists commit/tree and file/blob provenance, reuses unchanged or already-known blobs, records conservative renames/deletions, follows provider-ID-backed repository coordinate changes, and derives immutable source/evidence links from that history. Work items use provider ID plus `updated_at`; PR review activity uses an independent rendered-content digest so review edits and token-backed Review-thread current-state changes are versioned even when the PR timestamp is unchanged. It does not claim a complete Java AST or symbol/call graph, factory-inferred/classic-loop-or-resource-bound/reassigned local-variable types, overload or inherited dispatch resolution, authoritative Review-thread event timestamps, webhooks, polling, force-push reachability analysis, or destructive source invalidation. See [ADR 0012](docs/adr/0012-bounded-java-source-ingestion.md), [ADR 0014](docs/adr/0014-bounded-cross-file-java-types.md), [ADR 0015](docs/adr/0015-local-folder-repository-identity.md), [ADR 0016](docs/adr/0016-normalized-github-remote-identity.md), [ADR 0017](docs/adr/0017-bounded-cross-file-java-method-calls.md), [ADR 0018](docs/adr/0018-bounded-github-snapshot-import.md), [ADR 0019](docs/adr/0019-incremental-github-commit-snapshots.md), [ADR 0020](docs/adr/0020-derived-immutable-github-evidence-links.md), [ADR 0021](docs/adr/0021-versioned-github-work-items.md), [ADR 0022](docs/adr/0022-bounded-java-declared-receiver-calls.md), [ADR 0023](docs/adr/0023-versioned-github-pull-reviews.md), and [ADR 0024](docs/adr/0024-bounded-github-review-thread-state.md).

Implemented in this slice:

- `.java` upload validation and `source_type=java`, with source type included in duplicate-reuse semantics.
- A deterministic local parser for top-level types and conventional direct-member methods, including comment/string/text-block shielding while retaining exact chunk text.
- Stable one-based inclusive line ranges, hashes, structure paths, and chunk UUIDs for `code`, `comment`, `type`, and `method` chunks, with type annotations grouped into the type.
- `code_parsing` support in manual execution and the leased database worker.
- Desktop source-workspace upload, MD/JAVA labels, and Java chunk-kind display.
- A bounded source-structure endpoint and desktop outline for stable type/field/method symbols plus same-file unqualified/`this.` call hints, kept outside the formal graph.
- Separate desktop single-file and folder upload; folders ignore unsupported/empty files and import up to 50 Markdown/Java sources while persisting normalized relative paths. Failures are reported per file without rolling back successful uploads.
- Project-scoped top-level `extends`/`implements` resolution across at most 100 ready Java sources using explicit imports, same-package lookup, and wildcard imports, with ambiguity and truncation surfaced in the source outline.
- A stable local-folder repository UUID resolved from project, kind, and folder-root name; folder sources store repository-relative paths, deduplicate within that repository, and do not resolve Java types across repository boundaries.
- GitHub HTTPS, SCP-style SSH, and `ssh://` remotes normalize to a project-scoped owner/repository identity and canonical URL; users can register remote-only repositories or link an existing local-folder repository without contacting GitHub.
- A registered GitHub repository can be synchronized explicitly at its default branch or a requested ref; up to 50 supported blobs and 20 MiB enter the same immutable source/task workflow, with partial skips and truncation reported.
- Successful GitHub synchronization persists a commit/tree snapshot and per-file blob/status records; consecutive identical commits short-circuit, unchanged and known blobs avoid downloads, complete snapshots record conservative renames/deletions, and GitHub provider IDs preserve identity across remote coordinate changes.
- Source list/detail and formal graph/search/question evidence derive commit-pinned GitHub URLs from the latest non-deleted source occurrence; evidence links include exact line fragments while `project://` remains available.
- An explicit activity import reads at most 20 recently updated GitHub Issues/Pull Requests and 20 issue comments per item, plus 20 reviews, 20 inline review comments, and with a token 20 current-state Review threads per selected PR. Work-item versions follow `updated_at`; review snapshots follow their rendered-content digest. Both open the canonical conversation from source/evidence views.
- Direct type-qualified, current-type field, explicitly typed parameter, and direct method-local receiver calls resolve by imports/package to methods declared in other ready sources in the same repository, with conservative shadowing, name-only overload ambiguity, and bounded target metadata.

Acceptance still needed:

- Manually upload and parse representative Java files, including comments, string literals, text blocks, multiple top-level types, constructors, methods, and syntax the bounded parser intentionally leaves as type/code text.
- Configure a local DeepSeek key and verify a real model response against a short public Markdown note.
- Review evidence quality and model output on representative inputs; simulated tests do not establish real extraction quality.
- Verify the real project graph against native PostgreSQL in a browser, including empty, truncated, filtered, and time-filtered states.
- Retain PostgreSQL Worker/API concurrency and recovery validation; review/promotion repeated-confirmation contention has passed in a disposable schema.
- Evaluate semantic and hybrid ranking on representative native-PostgreSQL data with confirmed relationships; the current real-provider smoke project has seven indexed entities but no confirmed edges.

Project keyword, semantic-vector, explainable one-hop graph hybrid retrieval, and first-pass evidence-grounded answers are implemented. Entity disambiguation, question history, multi-turn Agent behavior, and streaming remain future work. See [ADR 0011](docs/adr/0011-synchronous-evidence-grounded-questions.md).

## Later phases

1. Representative real-answer acceptance and retrieval/prompt quality evaluation.
2. Extend Java resolution beyond the supported lexical blocks and constructor-initialized receivers and evaluate webhook-backed authoritative GitHub Review-thread events beyond the bounded GraphQL state snapshot.
3. Temporal evolution, governance, experiments, and deployment.

Markdown parsing, schema-constrained review, and confirmed-candidate graph persistence are complete as bounded slices.

Detailed deliverables, risks, and twelve-week scheduling are maintained in `docs/ROADMAP.md`.

## Planning rules

- Work on one bounded phase at a time.
- Confirm architecture-impacting choices with an ADR.
- Keep acceptance criteria observable and testable.
- Update this file when the active phase changes, not after every small task.
- Do not mark a phase complete only because documentation or scaffolding exists.
