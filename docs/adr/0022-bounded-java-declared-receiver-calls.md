# ADR 0022: Resolve bounded Java calls through declared method receivers

[简体中文](0022-bounded-java-declared-receiver-calls.zh-CN.md)

- Status: Accepted
- Date: 2026-10-21

## Context

ADR 0017 intentionally limited cross-file Java method hints to direct type-qualified and current-type field receivers. Representative service code also passes collaborators as method parameters or assigns them to simple method-local variables, so those calls remained disconnected even when the declared type was explicit and available inside the repository.

## Decision

- Extend the existing on-demand `cross_file_calls` derivation without changing the response shape, persistence model, repository/source/byte bounds, or formal-graph boundary.
- Read explicit declared types from method parameters and from single-variable declarations directly inside the method body. Resolve calls only after the local declaration appears.
- For an unqualified receiver, apply Java-like shadowing precedence: the latest eligible direct local declaration, then a method parameter, then a current-type field. An explicit `this.field` always selects the field. Direct uppercase type-qualified calls remain supported.
- Continue resolving declared types through explicit imports, the current package, and wildcard imports. Match target methods by name and preserve the existing `resolved`/`ambiguous` behavior and deterministic IDs.
- Ignore `var`, multi-variable declarations, nested-block locals, reassignment/data flow, chained/factory receivers, inherited dispatch, overload selection, and external classpaths.

## Consequences

- Common parameter-injected and simple method-local collaborator calls now link to repository-local method declarations while retaining exact call and target lines.
- Field shadowing is represented conservatively: `validator.run()` can follow a parameter/local declaration, while `this.validator.run()` continues to follow the field declaration.
- The result remains a bounded syntactic hint rather than a complete Java call graph. Complex scope, inference, and dispatch require a real parser and symbol solver before they can be claimed.
