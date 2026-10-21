# ADR 0026: Resolve Java local receivers within bounded lexical blocks

[简体中文](0026-scoped-java-local-receivers.zh-CN.md)

- Status: Accepted
- Date: 2026-10-21

## Context

ADRs 0022 and 0025 derive calls through direct method-body locals, including constructor-initialized `var`. Ordinary nested code remains disconnected, and a flat local-variable map cannot distinguish sibling blocks or restore an outer field after a local binding leaves scope.

## Decision

- Index method-body braces after comment/literal masking. Support ordinary brace blocks and braced `if`, `else`, `else if`, and `while` bodies. Track each block's parent and closing offset without introducing an AST dependency.
- Associate explicit local types and constructor-initialized `var` bindings with their containing block. A binding is visible after its declaration/initializer and before its block ends, including supported descendants. Select the latest visible local before parameters and fields; `this.field` still selects the field.
- Keep unsupported `var` initializers as unknown bindings for their lexical lifetime. They suppress field/type fallback inside that block, then allow the outer binding again after exit.
- Conservatively skip cross-file calls in unsupported braced scopes and their headers: `for`, resource/exception handling, `switch`, lambdas, anonymous classes, local types, and branches containing `instanceof`. Header declarations do not become method-wide locals. This does not implement all Java control-flow, pattern, capture, or scope rules.
- Preserve API shape, exact source/target lines, stable IDs, repository/source/result bounds, source chunks, persistence, and the formal-graph boundary. This extends the nested-local exclusions in ADRs 0022 and 0025 only for the supported brace forms.

## Consequences

The existing outline can link ordinary nested collaborators and distinguish sibling bindings while restoring outer fields and parameters after block exit. Unsupported regions may return fewer hints than before to avoid guessing through unknown local bindings. General inference, factory/chained `var` initializers, multi-variable declarations, reassignment analysis, overload selection, and inherited dispatch remain deferred.
