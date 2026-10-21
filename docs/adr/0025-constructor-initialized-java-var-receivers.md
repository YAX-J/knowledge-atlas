# ADR 0025: Infer bounded Java var receivers from constructor initializers

[简体中文](0025-constructor-initialized-java-var-receivers.zh-CN.md)

- Status: Accepted
- Date: 2026-10-21

## Context

ADR 0022 derives repository-local method calls through explicitly declared parameter and direct method-local receivers. A direct local such as `var validator = new Validator()` already names its type in the initializer, but the existing outline omits its later calls. Ignoring an unknown local can also incorrectly fall back to a same-name field or uppercase type.

## Decision

- Extend only direct method-body locals with a complete `new Type(...)` initializer, optionally preceded by `final`. Accept qualified type names, balanced generic arguments/diamond, and nested argument parentheses after comments and literals have been masked.
- Infer only the constructor's raw type name. Make it available after the complete initializer, then use the existing package/import lookup, repository boundaries, method-name ambiguity rules, and stable source/line IDs.
- Preserve an unknown binding for an unsupported `var` initializer. It shadows the same-name field/type rather than creating a guessed call; explicit `this.field` continues to select the field.
- Continue excluding factory returns, chained expressions, casts, arrays, conditional expressions, anonymous-class/braced initializers, nested-block locals, loop/resource-header bindings, general data flow, generic substitution, and overload/inherited dispatch.
- Keep source chunks, API shape, persistence, result bounds, and the formal-graph boundary unchanged. This supplements ADR 0022's former blanket exclusion of `var` for this constructor-only subset.

## Consequences

Common constructor-initialized collaborators appear in the existing source outline without a migration, frontend change, external compiler, or LLM call. The result remains a bounded syntactic hint; unsupported forms deliberately yield fewer links rather than false field/type fallbacks.
