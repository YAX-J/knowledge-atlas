# ADR 0040: Parse multiple code languages without changing knowledge authority

[简体中文](0040-multilanguage-source-parsing.zh-CN.md)

Status: Accepted

Date: 2026-10-23

## Decision

Add Python, JavaScript/JSX, TypeScript/TSX, Go, C, C++ and C# via pinned Tree-sitter language wheels. Centralize source extensions, media types and compatible parsing tasks. Extend existing uploads, Worker, GitHub synchronization, outlines and symbol search rather than creating a parallel ingestion or graph-writing pipeline. Retain Java's parser, symbol identities and repository analysis.

Use existing source type strings, `code_parsing` tasks and chunk schema; no database migration. Preserve exact whole-line evidence and deterministic IDs. Expose bounded/incomplete syntax explicitly, with no inferred cross-file relationships for new languages. Add optional `rescan` to discover new extensions in old same-commit snapshots without abandoning default caching. See [scope and limits](../MULTILANGUAGE_PARSING.md).

## Consequences

Dependencies include native wheels; deployment must install compatible pinned versions. Parsing is syntax-only, never compilation/execution or model invocation. Grammar upgrades require regression/evidence-identity review; do not destructively reparse promoted sources. Existing complete snapshots require an explicit rescan to discover newly supported files. Automatic knowledge, compiler semantics and internationalized UI are outside this decision.
