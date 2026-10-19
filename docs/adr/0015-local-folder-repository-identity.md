# ADR 0015 Identify local-folder source repositories within a project

[简体中文](0015-local-folder-repository-identity.zh-CN.md)

- Status: Accepted
- Date: 2026-10-19

## Context

Folder-relative paths make files recognizable, but they do not provide a stable scope for duplicate reuse or cross-file resolution. Project-wide matching can incorrectly combine identical files or equal package names from unrelated repositories. Browsers expose a selected folder's root name and relative file paths, but not a stable absolute path or Git remote.

## Decision

- Add `source_repositories` with a business UUID, `user_id`, `project_id`, `kind`, `name`, and timestamps. The first supported kind is `local_folder`.
- Resolve local repositories idempotently by `(user_id, project_id, kind, normalized root-folder name)` through `POST /projects/{project_id}/repositories/resolve`; provide a paginated project list endpoint.
- Add nullable `repository_id` to sources. Existing rows remain unassigned and require no destructive backfill.
- Require a normalized repository-relative path when an upload supplies `repository_id`. The desktop strips the browser root segment before uploading each folder file.
- Include nullable repository identity in duplicate-reuse scope. Identical bytes in the same repository reuse the first source and task; identical bytes in different repositories remain separate.
- Bound derived cross-file Java type resolution to the same repository. Unassigned legacy sources only resolve against other unassigned sources in the same project.
- Serialize repository resolution and duplicate upload checks with the existing PostgreSQL project-row lock.

## Consequences

Folder imports now have a stable business boundary suitable for later method resolution and incremental synchronization. Existing single-file and historical folder sources continue to work with `repository_id = null`. No source bytes or evidence are rewritten.

The local identity is intentionally weaker than Git identity. Two different folders with the same root name inside one project resolve to the same local repository, while renaming a root folder creates another identity. Git remote URL, provider repository ID, branch, commit SHA, file deletion, and change reconciliation remain future work. Changed bytes at an existing path still create a new immutable source rather than replacing or superseding the old one, so multiple ready versions of the same qualified Java type can coexist and are surfaced as ambiguous during cross-file resolution.

## Alternatives considered

- Continue using the whole project as repository scope: rejected because unrelated code trees can collide.
- Persist the browser's absolute folder path: rejected because browsers do not expose it reliably and local private paths should not be stored.
- Require Git metadata now: deferred so plain local folders continue to work before GitHub ingestion exists.
- Backfill repositories from the first segment of existing relative paths: rejected because historical paths may not represent one repository and automated reassignment could change deduplication or resolution semantics.
