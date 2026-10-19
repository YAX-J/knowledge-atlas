# ADR 0013 Derive bounded Java source structure outside the formal graph

[简体中文](0013-derived-java-source-structure.zh-CN.md)

- Status: Accepted
- Date: 2026-10-18

The cross-file limitation recorded here is expanded for bounded top-level type relationships by [ADR 0014](0014-bounded-cross-file-java-types.md); same-file method-call rules remain unchanged.

## Context

Java chunks preserve evidence, but a developer also needs a concise file outline and navigable method-call hints. Automatically promoting parser guesses into the reviewed knowledge graph would bypass the existing evidence and review boundary.

## Decision

- Provide `GET /api/v1/sources/{source_id}/code-structure` for parsed Java sources.
- Derive the response on demand from the immutable source. Do not add tables or write derived symbols and calls into the formal graph.
- Return stable, line-addressable type, conventional field, and method symbols. Bound the response to 200 symbols.
- Report only unqualified or `this.` calls that match a method name in the same file. A unique name is `resolved`; overload/name collisions are `ambiguous`. Deduplicate same-line calls and bound the response to 500 calls.
- Keep candidate extraction and manual review as the only path into formal knowledge.

## Consequences

The desktop source workspace can show useful code structure without a migration or a model call. Results remain deterministic for immutable source bytes and are clearly separate from confirmed knowledge.

This is not semantic Java resolution. It does not resolve receiver types, static-qualified calls, inheritance, dependency injection, cross-file symbols, external libraries, or dynamic dispatch. It may omit unconventional declarations and reports overloads as ambiguous.

## Alternatives considered

- Persist a separate code graph now: deferred until repository import and cross-file identity rules exist.
- Promote parser output directly into formal entities/relationships: rejected because it bypasses review.
- Use a complete compiler or tree-sitter immediately: deferred until repository-scale parsing justifies the dependency.
