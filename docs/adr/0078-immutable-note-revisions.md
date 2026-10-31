# ADR 0078: Editable notes with immutable revisions

[简体中文](0078-immutable-note-revisions.zh-CN.md)

Status: Accepted · 2026-10-31 · M3

Notes are project-scoped raw material. `notes` stores stable identity and a current revision pointer; `note_revisions` appends title, Markdown, parent, SHA-256, author origin and original artifact/task provenance. Existing revision content is never updated by the service. Human saves bind a request UUID and expected parent; stale saves return409 without replacing the draft. Same-UUID replay compares the original input and returns its immutable revision.

The editor debounces saves by600ms, preserves edits made during requests, isolates project responses and caches unfinished drafts in sessionStorage. Unknown transport outcomes require a GET or explicit same-UUID replay; reload never repeats a mutation. Conflicts pause autosave. History/citations open exact revisions as escaped text. Raw search scans at most100 current notes/200000 characters and reports truncation. Task attachments select at most20 exact revisions/200000 characters, not moving latest pointers.

Assistant drafts are editable notes with immutable provenance. Existing-note proposals contain full before/after content and the expected parent, and use ADR0079 approval. Editing a derived draft preserves its original citation record; this does not assert that edited prose remains supported by those citations.

`note_sources` maps an explicitly selected revision to one immutable Markdown source and parse task. Snapshot creation is idempotent and never creates formal graph records. Only the existing extraction and human review path promotes evidence. Note references use `kind=note`, note/revision UUIDs, title, hash, exact lines and quote, without fabricating source/chunk/evidence IDs. Formal evidence and evidence-claims-v3 remain unchanged.

Migration0022 adds three tables. Downgrade removes notes/history/mappings and needs a verified backup; it is maintenance, not business undo. PostgreSQL remains the only business store. No collaborative editor, generic memory store or new graph type is introduced.
