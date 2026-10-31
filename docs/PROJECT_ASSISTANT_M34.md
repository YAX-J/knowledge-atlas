# Project assistant M3 / M4

[简体中文](PROJECT_ASSISTANT_M34.zh-CN.md)

Implemented on `feat/project-agent`, 2026-10-31. [ADR0078](adr/0078-immutable-note-revisions.md) defines notes; [ADR0079](adr/0079-governed-assistant-actions.md) defines capabilities and approval. M5 and live model quality remain separate.

Use the existing native PostgreSQL, `backend/.venv`, `frontend/node_modules`, API, parsing worker and independent `python -m app.assistant_runner`. No new service or dependency is required. Source/business schema is `20261031_0023`; readiness rejects older databases. Existing v1 synchronous200 and v2 queued202 tasks retain their contracts and historical replay behavior.

## Notes and editable results

The Agent workspace includes a note editor with600ms autosave, immutable history, raw-note search, exact revision attachments and explicit source snapshots. Title is limited to120 characters; Markdown to60000. Searches scan at most100 current notes/200000 characters and expose truncation. Task attachments allow20 revisions/200000 characters. Source reads retain20 files/200000bytes/500chunks; derived imports may list more files but disclose read truncation.

Each edit binds its request UUID and expected parent. Concurrent edits return409 and preserve the local draft. Unknown results are read first or retried explicitly with the same UUID; reload only issues GETs. Drafts are cached per project/tab. Clean cached editors load current approved content; unfinished drafts pause for inspection. Historical citations open and focus the exact immutable revision. List refresh cannot replace editor navigation.

Agent-created notes remain raw drafts. A saved report preserves its original report and exact citations in revision provenance, including after human edits; those citations do not certify edited prose. Explicitly creating a source snapshot binds one original note revision. Parsing and extraction use that source; only human confirmation writes formal knowledge. Raw note citations never fabricate formal evidence IDs.

## One task with governed actions

Submit `protocol=assistant-task-v3`. Select source versions and attach exact note revisions. By default no write capability is granted. The UI exposes these optional `allowed_actions`:

| Capability | Result |
| --- | --- |
| `create_note_draft` | New editable draft, task provenance |
| `propose_note_revision` | Complete before/after proposal, expected revision; human approval |
| `request_source_parse` | Explicit note snapshot or deterministic source parsing |
| `import_repository_snapshot` | Submission-bound repository UUID + exact40-character lowercase SHA |
| `propose_knowledge` | Strict evidence-validated pending candidates |
| `propose_knowledge_change` | Candidate confirmation, merge, new→old SUPERSEDES or retirement proposal; human approval |
| `create_report_draft` | Typed report artifact using only actual task references |

Project overview/source/status/evidence/code/conflict/note reads also use the scoped gateway. Imported/snapshotted sources join scope only through persisted receipts. There are no shell, arbitrary-file, publishing, user-code execution or remote-write tools. Historical knowledge time excludes current attachments and write capabilities. Conflict inspection is a current-time hint, not a formal conclusion.

The runner saves a tool checkpoint then stops at `waiting_approval`. Review full proposed inputs, before records, target/evidence versions and proposal checksum. Approve or reject the exact operation. Changed objects save a conflict without applying the proposal; rejection leaves underlying candidates unchanged. An approval request binds request/operation UUIDs, proposal SHA and decision. Same-UUID replay is idempotent. Existing domain services apply mutations and receipts atomically; formal evidence/temporal/identity validators still apply.

Approval sends zero model requests. After all pending proposals settle, choose explicit continuation. It retains the task budget/checkpoint and supplies the actual outcome once, including exact newly confirmed evidence. Original knowledge search time stays fixed. Unknown model/write outcomes require acknowledgement and retain attempted counts. Cancellation/lease loss prevents late writes, including writes made after another transaction cancels a runner.

V3 shares8 model/16 tool attempts and0 embeddings,230seconds of execution time, across all roles. Coordinator permits8/16 within those totals; specialist roles retain4/8. V2 coordinator remains4/8. This supports fixed import→parse→extract candidates→proposal→human approval→formal-reference report in one task, without automatic paid retries. The deterministic acceptance path uses6 total model attempts including extraction.

## API additions

All paths are under `/api/v1`, scoped by the current actor and project:

| Method / path | Input / result |
| --- | --- |
| POST / GET `/projects/{project}/notes` | Create with request_id/title/markdown; paged list/search with query |
| GET / PUT `.../notes/{note}` | Current note; save request_id/expected_revision_id/title/markdown |
| GET `.../notes/{note}/revisions` | Paged immutable revision history |
| GET `.../notes/revisions/{revision}` | Exact original revision |
| POST `.../notes/revisions/{revision}/source` | Idempotent source/parse-task mapping |
| POST `.../assistant/tasks` | v3 capabilities, note_revision_ids and optional repository_id/repository_commit;202 |
| POST `.../assistant/tasks/{task}/approvals` | request_id/operation_id/proposal_sha256/decision |
| POST `.../assistant/tasks/{task}/artifacts/{artifact}/note` | request_id; editable provenance-preserving note |

Task reads add operations, unknown_operations, remaining and final_artifact_id. GET/events/artifact reads remain free. Reports use `assistant-report-v2`; note references contain note_id/revision_id/hash/lines/quote and source_id=null. Formal evidence and evidence-claims-v3 are unchanged. Thread and generic input APIs in the original plan remain prospective.

## Verification and migration

The user selected Agent-run verification, reusing installed dependencies and local substitutes. Full backend:1058 passed/13 skipped,95.43% coverage against90%. Final runtime/queue/notes/migration focus and native PostgreSQL checks additionally cover the human-pause event vocabulary. After the full run, the last39-pass/2-skip focus verifies completed specialist receipts and45K-character note proposals; complete before/after records stay in the human API while model tool receipts remain compact. Alias, merge membership, lifecycle and related edge history are bound even when the original entity row remains unchanged. Frontend:156 tests, coverage71.60% statements/76.20% lines, unchanged thresholds; production build passes. Native isolated upgrade/downgrade/upgrade and296 tests pass, including two consumers and independent-transaction cancellation. No live provider or GitHub traffic is used.

Desktop Chrome at1440×1000 covers autosave, historical reference after later edits, report-to-note conversion, note approval, candidate confirmation and formal references, explicit continue, read-only reload, project isolation/empty states, real Tab focus, panel scrolling and no horizontal clipping. Approval and reload preserved substitute counters; live requests remain0. Two editor navigation/cache races found in the browser are fixed and regression-tested. Temporary QA schemas/services are cleaned after verification.

Before business0021→0023, `output/backups/pre-m34-20261031-01/` received a checksum-verified 31-table snapshot. Restore into fresh `ka_restore_m34_20261031_01` passed structural/content fingerprints and was cleaned. Migration added5 tables; all30 old business-table content fingerprints stayed identical, and schema readiness passed. The redacted migration result is `migration.json` beside that archive. No business downgrade was performed. Downgrades delete new note/approval history and are maintenance operations requiring a verified backup.

Frozen experiments, grants, provider ledgers, historical scores and human grading0% stay unchanged. Substitute correctness does not establish semantic model quality, live GitHub acceptance or a hosted CI pass. M5 release/evaluation/demo work has not started.
