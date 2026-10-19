# ADR 0014 Resolve bounded cross-file Java type relationships on demand

[简体中文](0014-bounded-cross-file-java-types.zh-CN.md)

- Status: Accepted
- Date: 2026-10-19

[ADR 0015](0015-local-folder-repository-identity.md) narrows the current implementation from project scope to repository scope when a source has repository identity; legacy unassigned sources remain isolated together.

## Context

Persisted folder-relative paths and the source-level Java outline make files navigable, but a developer still cannot see whether a top-level type extends or implements another project source. A complete compiler-backed symbol graph needs repository identity, build configuration, classpaths, and stronger incremental-update semantics. ADR 0015 now supplies a bounded local-folder identity, while the remaining inputs are still unavailable.

## Decision

- Extend `GET /api/v1/sources/{source_id}/code-structure` with on-demand top-level `extends` and `implements` relationships scoped to the source's repository identity. Legacy sources without repository identity resolve only within the unassigned set of their project.
- Inspect only `ready` Java sources owned by the same user and project with the same nullable repository identity, including the selected source and at most 99 related sources. Bound related-source content reads to 20 MiB.
- Resolve targets by Java source declarations, explicit imports, same-package lookup, and wildcard imports. Do not guess unresolved external-library types.
- Return stable target symbol IDs, source IDs, persisted relative paths when available, source lines, and `resolved` or `ambiguous` status.
- Bound related types to 400 and type relationships to 500. Surface source or result limits through the existing `truncated` flag.
- Derive every response from immutable source bytes. Do not persist this structure or promote it into the reviewed formal graph.

## Consequences

The source workspace can now trace a useful subset of cross-file type hierarchy without a model call or new parser dependency. Repository, project, and user boundaries remain explicit, and duplicate fully qualified type declarations are visible as ambiguous rather than selected arbitrarily.

This is not complete repository-scale Java semantics. It does not resolve nested types, static imports, module/classpath precedence, cross-file method calls, inherited dispatch, dependency injection, generated sources, external libraries, or dynamic dispatch. Local-folder identity is based on the normalized root name and remains weaker than Git remote identity.

## Alternatives considered

- Persist a code graph now: deferred until repository identity and incremental synchronization rules exist.
- Use unique simple-name matching across the repository scope: rejected because it can invent relationships that Java import rules would not permit.
- Add a compiler or tree-sitter dependency now: deferred until broader cross-file method resolution justifies the operational and language-version cost.
