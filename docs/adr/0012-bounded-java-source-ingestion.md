# ADR 0012 Bounded Java source ingestion with line-preserving chunks

[简体中文](0012-bounded-java-source-ingestion.zh-CN.md)

- Status: Accepted
- Date: 2026-10-18

## Context

The Markdown-to-evidence workflow is complete enough to extend source coverage. The first code slice must preserve the existing evidence guarantees and remain usable without adding a parser runtime, repository credentials, or a new persistence model.

## Decision

- Accept UTF-8 `.java` files through the existing source upload endpoint, using `source_type=java` and task type `code_parsing`.
- Keep `SourceDocument`, `ProcessingTask`, and `SourceChunk` as the storage boundary. Duplicate reuse is scoped by user, project, source type, and content SHA-256.
- Use a deterministic local structural parser that blanks comments and literals while preserving offsets, identifies top-level Java types and conventional direct-member methods, and stores exact full-line slices as `code`, `comment`, `type`, or `method` chunks. Contiguous annotations immediately above a top-level type belong to its `type` chunk; comment-only lines outside methods use `comment` rather than being folded into a type fragment.
- Preserve one-based inclusive line ranges, content hashes, heading paths, and stable chunk UUIDs. A type path is `[type]`; a method path is `[type, method]`.
- Reuse the existing worker, manual task execution, candidate extraction/review, graph, search, and evidence-question flows after parsing.

## Consequences

Java files can enter the existing evidence workflow without a schema migration or third-party parser. Source-type validation prevents a file extension from selecting a different parser than the submitted type.

The parser is deliberately not a complete Java AST. It does not promise nested-type modeling, overload signatures, semantic resolution, call graphs, repository paths, Git URLs, GitHub import, or incremental repository synchronization. Those remain later Stage 4 slices.

## Alternatives considered

- Add tree-sitter immediately: deferred until symbol and call-graph requirements justify the dependency and grammar lifecycle.
- Model code symbols as formal graph entities during parsing: rejected because extraction and review remain the gate for formal knowledge.
- Clone repositories in the first code slice: deferred to keep authentication, repository lifecycle, and incremental updates separate from file parsing.
