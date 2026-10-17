# ADR 0006 Explicit DeepSeek candidates with evidence-gated review

[简体中文](0006-deepseek-candidate-review.zh-CN.md)

- Status: Accepted
- Date: 2026-10-17
- Extended by: [ADR 0007](0007-confirmed-postgresql-graph.md) — confirmation now promotes candidates into formal PostgreSQL graph tables.

## Context

The user reports native PostgreSQL 17/pgvector ingestion, duplicate reuse, restart persistence, and automatic parsing passed, authorizes the next development step, and selects the DeepSeek API. PostgreSQL contention/recovery fault injection remains outstanding. Model output needs an observable review boundary before formal graph storage exists.

## Decision

- Use a small HTTP adapter for the official DeepSeek chat endpoint with JSON output and local Pydantic validation. Keep endpoint/model/timeout configurable and the key in backend environment settings. Default to `deepseek-flash` per the current [official documentation](https://api-docs.deepseek.com/); tests simulate responses and do not establish real model acceptance.
- Invoke extraction only through an explicit synchronous source action, not uploads or the parsing worker. Enforce input/output limits and make no automatic paid-call retries. A frontend timeout does not cancel the server/provider request.
- Use task type `knowledge_candidates`; legacy `knowledge_extraction` remains parsing-only. Derive stable task/candidate UUIDs from source, prompt version, and local candidate IDs. Source locking serializes claims, execution UUIDs fence result writes, and expired tasks can be explicitly retried. A successful source/prompt-version result is reused even after a model-setting change; forced re-extraction is deferred.
- Validate allowed types, unique local IDs, same-batch relation endpoints, and exact quotes from scoped source chunks. Compute quote line positions server-side. Persist the whole validated batch as pending candidates together with successful task state, or persist none of it.
- Reuse `candidate_knowledge` for staged entities/relations and evidence metadata. Store model/prompt provenance in candidate payloads. Add `review_events` for actor, time, and before/after values. Review state and event writes share one transaction; project locks and conditional updates serialize decisions. Identical repeats are idempotent, changes to a resolved decision conflict, and relationships require confirmed endpoint entities.
- Confirmation marks a candidate accepted for later promotion. It does not create authoritative graph nodes, relationships, or temporal versions. The UI must state this boundary. Merge, undo, disambiguation, formal graph promotion, retrieval, and Agent answers are deferred. ADR 0007 later implements formal graph promotion while keeping the other items deferred.

## Consequences

The user can review source-grounded model proposals through real APIs and a source-scoped UI without giving the model direct write access to formal knowledge. Checking exact quotes establishes location fidelity, not semantic correctness; human review and real model quality evaluation are still required.

Schema migration `20261017_0004` is additive. Downgrading it drops review events but preserves candidate/source records. Native service setup and real model calls remain separate from isolated tests and simulated browser fixtures. Large inputs must be split manually; extraction is not queued, automatically batched, heartbeated, or automatically retried. Interrupted provider requests may have incurred a charge before an explicit retry.

## Alternatives considered

- Automatic extraction on upload: deferred to keep paid calls explicit and parsing independently usable.
- Direct model-to-graph writes: rejected because it bypasses validation and evidence review.
- Treat review confirmation as graph promotion before graph tables exist: rejected because it would misrepresent completion and obscure later consistency rules.
