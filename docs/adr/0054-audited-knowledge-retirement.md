# ADR 0054: Audited retirement without erasing historical knowledge

Status: Accepted · Date: 2026-10-26

[简体中文](0054-audited-knowledge-retirement.zh-CN.md)

## Decision

Allow an explicit human to retire a current active entity or relationship for correction or obsolescence, with a required reason and second UI confirmation. This is a narrow additional graph mutation boundary, implemented by retirement.retire and graph.apply_retirement, under the same project lock used by review/evolution/rebuild writes. Migration 20261026_0017 adds knowledge_retirements with scoped composite foreign keys, one owner, reason/category, effective time and immutable before/after snapshots.

Use server time and close valid_to atomically with the audit event. Preserve status, original candidate/review decisions, source/chunk/evidence, semantic vectors and identifiers. Half-open interval filtering excludes the item at/after retirement and preserves prior-time reads. Retiring an entity also hides incident relationships through the existing endpoint visibility rule, without rewriting their intervals. No hard archive flag is set because that would hide past queries. Pending evolution suggestions must revalidate and cannot revive a retired endpoint.

Client request UUIDs map to a deterministic user/project event UUID. Repeating an identical submission returns its original audit result; a changed payload with the same UUID conflicts. Another UUID for already closed knowledge conflicts. Unknown transport outcomes never automatically resend; explicit same-input retry reuses the UUID during the mounted workspace session. Project/user and archived-project boundaries apply to writes and paginated audit reads.

## Consequences

This records a correction by removing a mistaken item from current use; corrected content must pass the normal candidate review flow. It does not edit old summaries, reverse confirmations, merge entities, delete evidence, reopen intervals, schedule future retirement or backdate events. Prior historical views intentionally continue to show what was believed then. Snapshot visibility is not a guarantee that historical claims were true. Migration downgrade removes the audit table but never reopens intervals; keep a verified backup before downgrading to preserve audit records.

The UI shares the evolution mutation lock, clears stale search/question/comparison state after success, refreshes graph/index status, and provides paginated audits plus a historical detail/evidence link. “Active” remains the historical record status; valid_to decides current eligibility. Real PostgreSQL races and browser flows are recorded in [acceptance](../OPTIMIZATION_456_20261026.md).
