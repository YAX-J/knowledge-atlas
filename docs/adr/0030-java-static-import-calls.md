# ADR 0030: Resolve bounded repository-local Java static-import calls

[简体中文](0030-java-static-import-calls.zh-CN.md)

- Status: Accepted
- Date: 2026-10-22

## Context

The Java V1 index ignores static imports, leaving common unqualified utility calls without repository-local targets. Stage 4 continues to extend source analysis without executing builds or treating derived relationships as reviewed knowledge.

## Decision

- Index explicit and on-demand static imports separately from type imports. Resolve unqualified calls to static method candidates in other ready sources inside the existing user/project/repository and byte boundaries. Do not resolve imported nested types or fields.
- A current/inherited member name conservatively suppresses import fallback even when its argument count does not match. Incomplete member lookup also suppresses fallback. Explicit static imports for a name suppress wildcard imports, including when the explicit owner is absent. Qualified `this`/`super` calls never fall back to imports.
- Reuse bounded inherited method lookup, signature suppression, arity/varargs filtering, source-version ambiguity, deterministic target IDs/order, and output limits. Inherited class static methods may supply targets; interface static methods are not inherited.
- Exclude non-static/private methods. Imported types outside the current package must be public; methods declared outside that package must be public (including implicitly public interface methods). Full Java type/access/overload resolution remains outside this bounded subset.
- Keep API fields and persistence unchanged. For static-import links, `cross_file_calls[].receiver` is the marker `import static`, not a source receiver expression. Targets retain their original method symbols, paths, and lines; incomplete/ambiguous results are not compiler-certified calls. Do not add a compiler, dependency, migration, external request, or formal-graph write.

## Consequences

Utility calls can be followed to original source declarations through the existing outline. Conflicting imports and immutable versions remain ambiguous; missing dependencies and unsupported constructs do not produce invented targets. Conservative member precedence may omit calls a full compiler could resolve. Stage 4 and real-provider/native PostgreSQL acceptance remain separate work.

Acceptance uses `tests/test_java_static_imports.py` together with the [V1 regression commands](../JAVA_ANALYSIS_V1.md), then the full backend suite and `git diff --check`. Fixtures cover original IDs/lines, import precedence, accessibility, overloads, inherited statics, truncation, and API readiness/repository/project isolation.
