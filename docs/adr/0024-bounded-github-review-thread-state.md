# ADR 0024: Snapshot bounded GitHub review thread state through GraphQL

[简体中文](0024-bounded-github-review-thread-state.zh-CN.md)

- Status: Accepted
- Date: 2026-10-21

## Context

ADR 0023 imports Pull Request reviews and inline review comments through REST, including `in_reply_to_id`, but REST does not expose the complete thread grouping or current resolved state. GitHub GraphQL exposes Pull Request `reviewThreads` with current resolution, resolver, location, outdated state, and comment membership. GitHub exposes resolved/unresolved actions as prospective webhook events, but the query API does not provide an authoritative historical event timestamp.

## Decision

When `include_reviews=true` and `include_review_threads=true`, enrich each selected Pull Request review snapshot with the first 20 GraphQL review threads and the first 20 comment identifiers in each thread. Render the stable thread ID, current resolved/unresolved state, resolver when available, path and line range, subject, outdated state, and bounded comment membership into the same deterministic review Markdown. A state change therefore changes the activity digest and creates a new immutable review snapshot without depending on the base Pull Request `updated_at`.

GitHub GraphQL requires authentication. If no backend `GITHUB_TOKEN` is configured, keep the existing REST review import successful, render an explicit token-required marker, and return `review_threads_status=token_required`; never imply that an empty thread list was observed. A requested GraphQL call that fails or returns an invalid shape fails with the existing sanitized GitHub provider errors.

Persist thread counts, resolved counts, inclusion, and truncation metadata on `github_pull_review_versions`. `review_threads_truncated` covers either additional threads or additional comment memberships. The import remains explicit and bounded.

## Consequences

- Consecutive imports can show that thread state changed between snapshots, but cannot claim the exact resolution event time.
- Migration `20261021_0013` adds reversible metadata columns and preserves existing review versions with zero/not-included defaults.
- Public REST import still works without a token; complete thread-state enrichment needs a read-capable token and the configured GraphQL endpoint.
- Authoritative resolved/unresolved event history, webhook delivery, attachments, reactions, full pagination, polling, and destructive invalidation remain out of scope.

## Alternatives considered

- Infer resolution from REST replies: rejected because reply structure does not prove resolved state or identify the resolver.
- Present snapshot diffs as exact events: rejected because query snapshots do not provide authoritative action timestamps.
- Require GraphQL for every review import: rejected because it would regress unauthenticated public REST imports.
