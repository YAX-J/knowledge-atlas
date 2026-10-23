# ADR 0036: Infer bounded Java `var` receivers from static factory calls

[简体中文](0036-bounded-java-static-factory-var-receivers.zh-CN.md)

- Status: Accepted
- Date: 2026-10-23

## Context

Java analysis V1 can resolve explicitly typed locals and `var` locals initialized by a constructor. A common repository pattern instead uses `var value = Factory.create(...)`; the factory call is visible, but later calls on `value` remain unresolved even when the factory declaration and its return type are both present in the same imported repository snapshot.

## Decision

Recognize a complete type-qualified static factory initializer for an ordinary method-local `var`. Reuse repository-local type/import lookup, argument-count filtering and inherited method candidates. Infer the receiver only when every accessible static factory candidate has one resolvable, accessible repository-local return qualified name and all candidates agree on that name.

The inferred binding starts after the declaration terminator and follows the existing lexical-scope, shadowing, repository, readiness and analysis budgets. Ambiguous, missing, non-static, private or externally returned factories leave the binding unknown, so field/type fallback stays suppressed. The response shape, persistence model and formal graph are unchanged.

## Consequences

Calls after `var value = Factory.create(...)` can point to original repository method symbols without executing builds or writing derived code structure as reviewed knowledge. Duplicate factory/source versions remain visible through downstream ambiguity instead of being silently selected.

This is not general expression or data-flow inference. Chained, cast, conditional, instance-factory, unqualified/static-import factory, header-binding and reassignment forms remain unsupported, as do generic substitution, argument-type overload selection, external classpaths and runtime dispatch.

## Alternatives considered

- Use a full Java compiler or language server. Deferred because V1 must remain deterministic, dependency-free and safe for uploaded source snapshots.
- Infer from naming conventions or the assigned variable name. Rejected because it would fabricate receiver types without source evidence.
- Pick the first matching factory overload or return version. Rejected because bounded/immutable source sets can legitimately contain ambiguity.
