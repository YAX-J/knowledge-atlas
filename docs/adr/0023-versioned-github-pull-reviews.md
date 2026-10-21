# ADR 0023: Version bounded GitHub Pull Request review activity independently

[简体中文](0023-versioned-github-pull-reviews.zh-CN.md)

- Status: Accepted
- Date: 2026-10-21

## Context

The existing explicit GitHub activity import versions Issue and Pull Request Markdown by provider item ID, `updated_at`, and comment profile. Pull Request reviews and inline review comments are separate GitHub resources. Their content can change without a reliable corresponding change to the Pull Request `updated_at`, so folding them into the work-item key could incorrectly reuse stale review text.

## Decision

For every selected Pull Request with `include_reviews=true`, read at most 20 Pull Request reviews and 20 inline review comments from the first REST page. Use the response `Link` header to report whether either collection has another page. Preserve the review state, actor, submission time, body, commit and URL; preserve inline-comment path/line, actor, timestamps, body, URL, and `in_reply_to_id` when available.

Render that activity into a deterministic Markdown source separate from the base Pull Request source. Hash the complete rendered bytes with SHA-256. `github_pull_review_versions` maps repository, provider Pull Request ID, and activity digest to the immutable source and parsing task. Reimporting identical activity reuses the source/task; any rendered review change creates a new review snapshot even when the base Pull Request version is unchanged. Empty activity is also a versioned snapshot so later removal is observable.

Review sources use the canonical Pull Request URL for external navigation and enter the existing Markdown parsing, evidence, review, and promotion flow. The import remains explicit and does not make a background GitHub request.

## Consequences

- Work-item version compatibility remains unchanged; migration `20261021_0012` only adds an independently reversible table.
- One selected Pull Request can create two source versions: the base conversation and its review activity.
- Review edits are detected by reading the bounded review endpoints on every explicit reviewed import, even when the base Pull Request source is reused.
- `in_reply_to_id` preserves a reply link, but the REST snapshot does not claim complete thread grouping or resolved/unresolved state.
- Review events, attachments, reactions, later pages, webhooks, polling, and destructive invalidation remain out of scope.

## Alternatives considered

- Add review fields to the work-item unique key: rejected because changing that key complicates rollback and couples review changes to the base conversation version.
- Depend on Pull Request `updated_at`: rejected because it cannot reliably identify independent review-resource changes.
- Use GraphQL review threads now: deferred until complete thread and resolution semantics are required.
