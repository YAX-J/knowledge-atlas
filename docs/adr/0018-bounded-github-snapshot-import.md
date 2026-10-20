# ADR 0018: Import bounded GitHub repository snapshots explicitly

[简体中文](0018-bounded-github-snapshot-import.zh-CN.md)

- Status: Accepted
- Date: 2026-10-20

## Decision

An already registered GitHub repository may be synchronized only through an explicit project-scoped API or UI action. The backend resolves the requested branch, tag, or commit ref (or the repository default branch), reads its commit and recursive Git tree through GitHub REST, and imports at most 50 non-empty UTF-8 `.md`, `.markdown`, and `.java` blobs through the existing source-ingestion service.

One synchronization downloads at most 20 MiB in total and retains the existing 10 MiB per-source limit. Files are processed in stable path order. Each accepted blob reuses the existing repository-scoped content-hash deduplication and creates the existing parsing task when it is new. A bad text file is reported as skipped without rolling back files already imported. GitHub tree truncation, the file limit, and the aggregate byte limit are exposed as a truncated result.

Public repositories work without credentials. A private repository may use an optional backend-only `GITHUB_TOKEN` with read-only Contents permission. The token is never returned to the browser or persisted as business data. Provider requests use a configured GitHub API base URL, a pinned API version, bounded timeouts, and sanitized application errors.

## Consequences

- GitHub content now enters the same immutable source, parsing, evidence, and review pipeline as local uploads; it does not bypass validation or human review.
- Remote-only and local-folder repositories linked to GitHub share the same explicit synchronization operation and repository boundary.
- Repeating a snapshot import is idempotent for unchanged bytes and returns reused source/task identifiers.
- The response identifies the resolved commit SHA, but this slice does not persist commit metadata on each source, import commit messages, generate immutable GitHub evidence URLs, detect renames, delete removed files, or perform scheduled/incremental branch synchronization.
- Recursive tree responses that GitHub marks as truncated remain partial. Traversing subtrees, webhook delivery, GitHub Apps, Issues, and Pull Requests are deferred.
