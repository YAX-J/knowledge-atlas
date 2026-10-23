# ADR 0038: Infer Java factory receivers in loop and resource headers

[简体中文](0038-java-header-factory-receivers.zh-CN.md)

- Status: Accepted
- Date: 2026-10-23
- Extends: [ADR 0037](0037-unqualified-java-factory-receivers.md), replacing its exclusion of supported header-bound factory locals

## Context

Bounded Java analysis supports constructor-initialized `var` in braced classic-for and resource-try headers, and static factory inference in ordinary method-body declarations. `try (var resource = Factory.open())` and equivalent loop declarations therefore leave receivers unknown despite available factory and return declarations.

## Decision

Preserve unresolved `var` header initializers as internal parsing metadata. Resolve them when lexical processing reaches the body opening, using the same static factory lookup, arity filtering, accessibility, agreed return-type and resolved-identity rules as method-body locals. Process headers and body declarations in source order. Within resource specifications, add bindings in declaration order so previous names shadow factory qualifiers and later names do not affect earlier initializers.

Returned bindings are visible only in the supported braced body and its nested scopes. They expire before catch/finally and sibling scopes. Header expressions still produce no call edges. Unknown/unsupported initializers preserve unknown bindings and suppress field/type fallback. Explicit types, constructor `var`, enhanced-for and catch bindings retain their existing behavior.

## Consequences

Classic-for single declarations and resource-try single/multiple declarations can resolve later receiver calls to original repository method UUIDs and lines. Duplicate return-source versions retain ambiguity. Existing repository/readiness limits, output budgets, API shapes, persistence and reviewed-knowledge boundaries remain unchanged. No compiler, provider, migration or automatic graph write is introduced.

Unbraced controls, multi-declarator classic-for headers, annotated/complex unsupported headers, instance/chained/cast/conditional factory inference, generic substitution and runtime dispatch remain excluded. Header calls are deliberately omitted, and factory inference continues to require the relevant imported declarations.
