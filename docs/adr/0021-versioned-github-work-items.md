# ADR 0021: Import bounded GitHub work items as immutable source versions

[简体中文](0021-versioned-github-work-items.zh-CN.md)

- Status: Accepted
- Date: 2026-10-21

## Decision

Knowledge Atlas imports GitHub Issues and Pull Requests only through an explicit repository action. One request reads at most 20 recently updated work items and, when requested, at most 20 issue comments per item. Pull Requests include available head, base, and merged metadata. The imported representation is deterministic Markdown and enters the existing repository-scoped Markdown parsing and evidence workflow.

Each provider item ID, GitHub `updated_at` value, and comment-inclusion profile identifies an immutable imported version. Repeating the same version/profile reuses its source and parsing task; a later `updated_at` or a different comment profile creates another version record instead of overwriting prior evidence. `github_work_item_versions` stores the provider identity, canonical conversation URL, state, title, comment-inclusion flag, imported comment count, truncation flag, source, and task.

GitHub work-item evidence opens the canonical Issue or Pull Request conversation. Its stored source lines refer to the imported Markdown snapshot; unlike repository files, GitHub does not provide an immutable line-fragment URL for conversation bodies and comments.

## Consequences

- Remote edits cannot silently replace text already used by candidates or formal evidence.
- Issue/PR content reuses the existing parser, worker, review, graph, retrieval, and question path.
- Import remains bounded, explicit, project-scoped, and token-isolated in the backend.
- A work-item source is immutable locally, but its canonical GitHub conversation URL is mutable and does not prove the historical text by itself.
- Review comments, review threads, events, attachments, reactions, automatic polling, webhooks, deletion propagation, and exhaustive pagination are not included in this slice.
