# ADR 0037: Resolve unqualified Java factory receivers

[简体中文](0037-unqualified-java-factory-receivers.zh-CN.md)

- Status: Accepted
- Date: 2026-10-23
- Extends: [ADR 0036](0036-bounded-java-static-factory-var-receivers.md)

## Context

Factory-based `var` inference currently accepts `Type.create(...)`. Static factories are also called as `create(...)` from the current type or through static imports. Leaving those locals unknown omits useful source links even when the repository contains the complete declarations.

## Decision

Accept complete unqualified factory initializers in ordinary method-body `var` declarations. Look up current and inherited members first. Any member name suppresses static-import fallback, even if its argument count or static modifier cannot support inference. An unqualified private static member can supply a return type only when declared in the exact current type. Otherwise reuse explicit/wildcard static-import lookup and its explicit-name precedence. Missing selected import owners or truncated member lookup keep the result unknown.

After arity/varargs filtering, member/type-qualified candidates must all be accessible static methods. Imported candidates follow the existing static-import access rules. Every selected factory must return one accessible repository-local qualified type name, and all selected factories must agree. Preserve original downstream method UUIDs, line ranges, duplicate-version ambiguity, lexical binding lifetimes, and source/readiness/repository boundaries.

Also suppress type-qualified factory inference when a supported local, parameter or current-type field shadows the qualifier's first name. Method type parameters cannot be mistaken for same-named source types. Existing API shapes, storage, migrations and formal knowledge semantics remain unchanged.

## Consequences

Both `var value = create()` and `var value = Type.create()` can support subsequent method links using source declarations. Ambiguous or incomplete return information leaves the local unknown and continues to suppress field/type fallback. No builds, provider calls or automatic knowledge writes are needed.

This extends only the supported line-oriented method-local subset. General expression inference, instance factories, chained/cast/conditional initializers, `this`/`super` factory qualifiers, header-bound factory locals, reassignment, generic substitution and argument-type overload selection remain deferred. Unknown selected wildcard-import owners conservatively reduce recall.
