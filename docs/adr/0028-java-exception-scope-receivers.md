# ADR 0028: Resolve Java calls within bounded exception scopes

[简体中文](0028-java-exception-scope-receivers.zh-CN.md)

- Status: Accepted
- Date: 2026-10-21

## Context

ADR 0026 excludes exception-handling regions. Plain try/finally bodies and explicitly typed catch parameters provide enough lexical information to link repository-local collaborators without solving exception flow. ADR 0027 already introduces body-scoped header bindings for enhanced-for elements.

## Decision

- Support plain `try` and `finally` brace blocks using the existing local declaration lifetimes, supported descendants, unknown `var` shadowing, and outer-binding restoration.
- Reuse body-scoped header bindings for unannotated catch parameters. A single simple or qualified type, optionally preceded by `final`, resolves through the existing package/import and repository lookup. The binding exists only within its own catch body and supported descendants; it never leaks into sibling catches, finally, or subsequent code.
- Retain an unknown binding for a multi-catch union such as `A | B error`. Do not arbitrarily choose an alternative or infer a common superclass. Calls on that receiver cannot fall back to a same-name field/type; other receivers in the catch body may still resolve. Explicit `this.field` continues to select the field.
- Keep resource-try headers and bodies excluded. Following supported catch/finally bodies resolve independently, without importing resource variables. Unsupported ancestors and annotated catches remain excluded; inherited dispatch, exception-path analysis, general inference, and reassignment/data flow remain deferred.
- Preserve response shapes, source/target lines, stable IDs, repository/source/result bounds, source chunks, persistence, and the separation from the reviewed formal graph. This supplements ADR 0026's exception-region exclusion; no migration, external service, or frontend change is required.

## Consequences

Exception-handling collaborators can appear in the existing source outline while lexical isolation remains explicit. Results are bounded syntactic hints, not exception-flow analysis or a complete call graph. A method inherited from an external exception superclass does not become a repository-local target merely because its receiver is a catch parameter.
