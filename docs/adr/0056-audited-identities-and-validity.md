# ADR 0056 Audited identities and historical validity

[简体中文](0056-audited-identities-and-validity.zh-CN.md)

- Status: Accepted
- Date: 2026-10-26

## Decision

Use additive EntityAlias/EntityMerge/KnowledgePeriod/KnowledgeOperation tables. Explicit project-locked idempotent human operations preserve original UUIDs, evidence and edges; graph/search/vector reads canonicalize at query time. Native embeddings retain original-owner text so current merges cannot contaminate historical vectors. Reopening a record saves its previous closed interval. Reasoned group replacement is atomic, same-type, cycle-checked and bounded to 10×10; only independent linear replacement may be reversed. Reject dependent reversal rather than rewriting audit history.

## Consequences and alternatives

Physical destructive merges were rejected because they lose provenance and break historical reads. Automatic model decisions remain proposals. Downgrade removes new history and requires a backup; this is not a data undo operation.
