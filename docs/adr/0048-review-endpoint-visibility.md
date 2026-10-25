# ADR 0048: Relation review dependency visibility

[简体中文](0048-review-endpoint-visibility.zh-CN.md)

Status: Accepted

Date: 2026-10-25

## Decision

Review listing enriches each relation with an `endpoints` snapshot containing unique accessible entity candidate IDs, names and review statuses. Resolve responses and entity candidates default to an empty list. Enrichment uses one bounded lookup for at most twice the page size, independently of the outer status/kind/text filters and pagination. Every endpoint must match the relation's user, project, source, successful extraction task and entity kind. Missing or incompatible endpoints are omitted; no foreign name or status is exposed.

The review UI shows source and target states even when their cards are filtered out or on another page. Single confirmation/edit-confirm requires both endpoints confirmed. Batch confirmation also accepts a pending endpoint explicitly selected as an entity on the current page; it never adds an endpoint automatically. Missing/rejected/unselected dependencies disable final confirmation and show named explanations. Explicit rejection remains available. An entity-list navigation action resets filters and selections and focuses the review heading; it performs no review or model call.

## Consequences

Users discover dependency problems before submitting a review. These are read-time snapshots and may become stale; backend project locking, authoritative dependency/evidence revalidation, audit idempotency and atomic rollback remain the final authority. This changes no promotion rule, persisted schema, endpoint identity, undo policy or model behavior. No migration or dependency is required.
