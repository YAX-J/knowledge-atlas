# ADR 0039: Review cross-source knowledge evolution explicitly

[简体中文](0039-reviewed-knowledge-evolution.zh-CN.md)

- Status: Accepted
- Date: 2026-10-23

## Decision

Add `knowledge_changes` (migration `20261023_0015`), a separate cross-source review boundary, without weakening candidate promotion's same-source/same-task endpoints or fabricating extraction tasks. Only confirmed records are authoritative evolution links. The ordinary graph remains time-visible semantic knowledge; a dedicated history API displays expired endpoints and replacement links.

Human proposals classify distinct, same-type, active formal entities in one user/project as `SUPERSEDES`, `SUPPLEMENTS`, or `CONFLICTS_WITH`. Each requires a reason and a still-verifiable formal evidence UUID from either endpoint; both endpoints must retain valid verbatim evidence. No model is called. Identical normalized requests reuse stable UUIDs. Proposing/rejecting does not change formal knowledge.

Confirmation locks the project, rereads and revalidates the proposal/endpoints/evidence/time. Graph service mutation remains explicit: `promote_candidate` creates extracted knowledge, `apply_reviewed_change` applies reviewed evolution. Resolution, immutable before/after snapshots and endpoint updates commit atomically. Same-action repeats are idempotent; reversal is unsupported.

Replacement direction is **new → SUPERSEDES → old**. Old validity ends and new validity begins at `effective_at`; old status becomes `superseded`. Intervals are half-open `[valid_from, valid_to)`. V1 rejects future dates and dates before either endpoint's current start; no source-text dating, backdating before promotion, scheduling, chain merging, branches or cycles. Active endpoints and at most one confirmed predecessor per new entity enforce a linear chain under the lock. Supplements/conflicts record classification without changing validity or silently marking facts true/false.

History enforces user/project and unarchived-project scope, follows only confirmed replacements with cycle protection, and caps at 100 entities/200 changes. Graph/search/questions retain existing temporal and both-endpoint visibility. An extracted `SUPERSEDES` semantic assertion does not mutate intervals: explicit change review is required.

Governance reads at most 1,000 current entities, returning 200 findings by default (maximum 500): missing valid verbatim evidence, normalized same-type/equal-name duplicates or different-summary possible conflicts, and nodes without visible semantic or confirmed evolution relationships. Normalization uses NFKC/casefold/whitespace; name groups compare to their first entity, not exhaustive semantic pairwise inference. Findings are not persisted candidates or automatic repairs. Omissions set `truncated`.

## Consequences

- Downgrading `0015` drops evolution proposals/audit links; it does not undo committed entity intervals. Back up first and do not downgrade a business schema as an acceptance step.

- Preserve extraction review, original evidence, UUIDs and time/archive filtering. Evolution remains separate from one-hop semantic retrieval.
- Frontend adds historical queries, explicit review, evidence-linked chronological chains and read-only checks; historical views cannot mutate knowledge.
- No merging/disambiguation, automatic semantic conflict inference, undo, arbitrary metadata editing, model-quality claim or question persistence.
- PostgreSQL acceptance must use an explicitly schema-qualified Alembic version table and check all local tables before tests. `search_path=temp,public` alone is unsafe: Alembic or queries can fall back to existing public tables. Only the generated schema may be removed.
