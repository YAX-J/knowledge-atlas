# ADR 0027: Resolve Java receivers through bounded enhanced-for elements

[简体中文](0027-enhanced-for-java-receivers.zh-CN.md)

- Status: Accepted
- Date: 2026-10-21

## Context

ADR 0026 indexes lexical brace scopes but excludes all `for` bodies. A common repository-local call such as `for (Validator item : items) { item.validate(); }` already declares the element type and can reuse the same bounded type lookup without collection inference or a compiler dependency.

## Decision

- Recognize unannotated single-element enhanced-for declarations with braced bodies, optional `final`, and simple, qualified, or generic types after comment/literal masking. Reuse the existing raw-type lookup; do not substitute generic arguments or infer a collection's element type.
- Add the element binding from the body's opening brace to its closing brace, visible in supported descendants. Preserve sibling isolation, outer-binding restoration, and the explicit `this.field` override. An unsupported ancestor still excludes the entire region.
- Keep enhanced-for `var` and array element variables as unknown bindings. Their body calls must not fall back to a same-name field or uppercase type; other explicitly typed receivers inside the body can still resolve.
- Omit all enhanced-for header calls. The iterable expression is outside the element variable's body scope, and this slice does not claim expression/control-flow resolution.
- Traditional `for`, resource/exception scopes, annotated enhanced-for bindings, unbraced loops, and other unsupported execution scopes remain outside this subset. Preserve the API shape, stable source/line IDs, repository/result limits, source chunks, persistence, and formal-graph boundary.
- Supplement ADR 0026's blanket `for` exclusion only for this enhanced-for subset; no migration or frontend change is required.

## Consequences

Explicitly typed loop collaborators become visible in the existing source outline, including nested and sibling loops. Unknown element bindings remain conservative instead of generating guessed links. Collection inference, generic substitution, reassignment/data flow, overload selection, inherited dispatch, and complete Java semantics remain deferred.
