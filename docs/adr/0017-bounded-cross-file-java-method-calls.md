# ADR 0017 Resolve bounded cross-file Java method calls on demand

[简体中文](0017-bounded-cross-file-java-method-calls.zh-CN.md)

- Status: Accepted
- Date: 2026-10-19

## Context

The source-structure view already derives same-file calls and repository-scoped cross-file type relationships, but it cannot connect a common service call such as `validator.validate()` to a method declared in another uploaded source. A complete Java semantic engine would require classpaths, overload signatures, inheritance, generics, local data flow, and build-system integration, which is too large for the current bounded ingestion slice.

## Decision

- Extend `GET /sources/{source_id}/code-structure` with on-demand `related_methods` and `cross_file_calls`; do not add persistence tables or formal graph records.
- Inspect only ready Java sources inside the current repository boundary, retaining the existing limit of 100 sources and 20 MiB of related source text.
- Resolve two explicit receiver forms: conventionally uppercase direct type-qualified calls such as `OrderValidator.normalize()`, and calls through a direct field of the current top-level type such as `validator.validate()` or `this.validator.validate()`.
- Resolve receiver types with the existing explicit-import, same-package, and wildcard-import rules. Return only methods declared directly on the matched top-level type in another source.
- Match methods by name only. A single candidate is `resolved`; overloads, duplicate immutable source versions, or duplicate qualified types are `ambiguous`.
- Bound the response to 500 related methods and 500 cross-file calls, preserve exact call and target lines, and discard relationships whose targets are omitted by truncation.

## Consequences

The desktop source outline can now show useful repository-local method edges without changing immutable source data or bypassing reviewed knowledge promotion. Target IDs reuse the same deterministic method-symbol scheme as the target source's own structure view.

This remains a syntactic hint, not a Java call graph. It does not resolve local variables, parameters, factory/chained receivers, inherited methods, interfaces to implementations, static imports, argument types, overload selection, generics, generated sources, external libraries, dependency injection, or dynamic dispatch. A field's declared type is used without data-flow analysis, and GitHub remote-only repositories still contain no source text to analyze.

## Alternatives considered

- Add a full Java parser and symbol solver now: deferred until representative repositories show that the bounded rules are insufficient for the graduation-project evaluation.
- Persist derived calls in graph tables: rejected because unreviewed parser hints are not formal knowledge.
- Guess local-variable and parameter types with regular expressions: rejected because shadowing and nested scopes would make the confidence boundary unclear.
