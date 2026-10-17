# Architecture Decision Records

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

Do not reuse a number. Superseded records remain in the repository.

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
