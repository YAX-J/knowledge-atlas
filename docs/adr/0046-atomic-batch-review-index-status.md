# ADR 0046: Explicit atomic batch review and read-only index status

[简体中文](0046-atomic-batch-review-index-status.zh-CN.md)

Status: Accepted

Date: 2026-10-25

## Decision

Add `POST /projects/{project_id}/reviews/resolve-batch` with one source UUID, 1–100 unique candidate UUIDs and a confirm/reject action. Validate the complete selection in the active user's project and source before processing. Hold the project lock, order entities before relationships and reuse the existing review/promotion path without intermediate commits. Commit once after every selected item succeeds; otherwise roll back all candidate changes, audit events and formal knowledge writes. Same-action retries remain idempotent. Relationships still require confirmed same-task endpoints; selecting a relationship does not implicitly select or confirm its endpoints. The response preserves caller selection order.

The frontend selects only visible pending candidates and requires a named preview plus explicit final action. Page changes discard hidden selections, unsaved edits block bulk actions, and review requests lock project/source/navigation context. A request timeout may leave an uncertain client result; users refresh or safely retry the same action. No undo or automatic confirmation is introduced.

Add provider-free `GET /projects/{project_id}/embeddings/status?valid_at=...`. Count eligible and matching indexed entities in the same user/project/effective-time scope. Inspect at most 1000 entities, rebuilding their canonical name/summary/evidence text hashes using the same ordering as index construction. Matching-model/dimension rows with changed hashes are stale; rows without a matching model/dimension are missing. Counts of eligible/indexed/missing cover the whole scope; current/stale counts cover the inspected subset only. Explicitly return scan limits and truncation. Configuration availability is a boolean, with no secrets or provider connectivity check. Read-only inspection never builds vectors.

Keep explicit index rebuild and existing search defaults. Refresh inspection after rebuild and ignore late responses after project/time changes. Status is not an answer-quality guarantee. No database migration is needed.

## Consequences

Batch review reduces repeated clicks while preserving existing provenance, audit and transaction boundaries. Index status distinguishes full row coverage from actual content freshness. In large projects, truncation means unseen stale rows may exist. Rebuild still covers the existing non-archived scope, while inspection follows the selected effective time. Entity merging, review reversal, automatic indexing and new model-quality claims remain outside this change.
