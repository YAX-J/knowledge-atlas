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
