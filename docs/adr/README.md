# Architecture Decision Records

[简体中文](README.zh-CN.md)

Architecture Decision Records capture durable choices that affect multiple components, data semantics, security, deployment, or future implementation work.

## When to add an ADR

Add an ADR when a decision changes one or more of the following:

- Source-of-truth or cross-database synchronization rules.
- Knowledge entity, relationship, evidence, or temporal semantics.
- Public API conventions.
- Major framework, storage, queue, model-provider, or deployment choices.
- Security boundaries or handling of private developer data.

Small refactors and local component choices do not require an ADR unless they constrain future work.

## File naming

Use a four-digit sequence and a short lowercase slug:

```text
0001-postgresql-source-of-truth.md
0002-native-svg-for-prototype-graph.md
```

Do not reuse a number. Superseded records remain in the repository. Chinese companions use the same sequence and a `.zh-CN.md` suffix; they do not allocate another number.

## Status values

- `Proposed`: under discussion.
- `Accepted`: current decision.
- `Superseded`: replaced by a newer ADR.
- `Rejected`: considered but not adopted.

## Template

```markdown
# ADR NNNN Decision title

- Status: Proposed
- Date: YYYY-MM-DD

## Context

What problem or constraint requires a decision?

## Decision

What is being decided?

## Consequences

What becomes easier, harder, required, or intentionally unsupported?

## Alternatives considered

Which credible alternatives were evaluated and why were they not selected?
```

Update related architecture, API, knowledge-model, and setup documents when an ADR changes their assumptions.

## Existing decisions

- [ADR 0001: PostgreSQL as the source of truth](0001-postgresql-source-of-truth.md) (superseded by ADR 0005)
- [ADR 0002: Native SVG for the prototype graph](0002-native-svg-for-prototype-graph.md)
- [ADR 0003: Persist Markdown chunks and run parsing explicitly](0003-markdown-parsing-execution.md)
- [ADR 0004: Database-backed parsing worker with execution leases](0004-database-backed-parsing-worker.md)
- [ADR 0005: Use PostgreSQL only and defer Neo4j](0005-postgresql-only-storage.md)
- [ADR 0006: Explicit DeepSeek candidates with evidence-gated review](0006-deepseek-candidate-review.md)
- [ADR 0007: Promote confirmed candidates into the PostgreSQL graph](0007-confirmed-postgresql-graph.md)
- [ADR 0008: Evidence-backed project keyword search](0008-project-keyword-search.md)
- [ADR 0009: Build the formal-knowledge semantic index explicitly](0009-explicit-semantic-index.md)
- [ADR 0010: Explainable hybrid retrieval with one-hop graph signals](0010-explainable-hybrid-graph-retrieval.md)
- [ADR 0011: Synchronous evidence-grounded questions with validated citations](0011-synchronous-evidence-grounded-questions.md)
- [ADR 0012: Bounded Java source ingestion with line-preserving chunks](0012-bounded-java-source-ingestion.md)
- [ADR 0013: Derive bounded Java source structure outside the formal graph](0013-derived-java-source-structure.md)
- [ADR 0014: Resolve bounded cross-file Java type relationships on demand](0014-bounded-cross-file-java-types.md)
- [ADR 0015: Identify local-folder source repositories within a project](0015-local-folder-repository-identity.md)
- [ADR 0016: Normalize GitHub remote identity before repository import](0016-normalized-github-remote-identity.md)
- [ADR 0017: Resolve bounded cross-file Java method calls on demand](0017-bounded-cross-file-java-method-calls.md)
- [ADR 0018: Import bounded GitHub repository snapshots explicitly](0018-bounded-github-snapshot-import.md)
- [ADR 0019: Persist incremental GitHub commit snapshots](0019-incremental-github-commit-snapshots.md)
- [ADR 0020: Derive immutable GitHub evidence links from snapshots](0020-derived-immutable-github-evidence-links.md)
- [ADR 0021: Import bounded GitHub work items as immutable source versions](0021-versioned-github-work-items.md)
- [ADR 0022: Resolve bounded Java calls through declared method receivers](0022-bounded-java-declared-receiver-calls.md)
- [ADR 0023: Version bounded GitHub Pull Request review activity independently](0023-versioned-github-pull-reviews.md)
- [ADR 0024: Snapshot bounded GitHub review thread state through GraphQL](0024-bounded-github-review-thread-state.md)
- [ADR 0025: Infer bounded Java var receivers from constructor initializers](0025-constructor-initialized-java-var-receivers.md)
- [ADR 0026: Resolve Java local receivers within bounded lexical blocks](0026-scoped-java-local-receivers.md)
- [ADR 0027: Resolve Java receivers through bounded enhanced-for elements](0027-enhanced-for-java-receivers.md)
- [ADR 0028: Resolve Java calls within bounded exception scopes](0028-java-exception-scope-receivers.md)
- [ADR 0029: Package bounded repository-local Java analysis V1](0029-java-analysis-v1.md)
