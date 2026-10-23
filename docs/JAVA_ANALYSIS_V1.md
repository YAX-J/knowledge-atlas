# Repository-local Java analysis V1

[简体中文](JAVA_ANALYSIS_V1.zh-CN.md)

V1 is a bounded, read-only source outline and call-candidate analysis, not a Java compiler or runtime call graph. Results come from immutable uploaded/parsed sources, retain original lines and deterministic symbol IDs, and never bypass knowledge review or enter the formal graph automatically. Stage 4 also contains separate GitHub and evaluation work; this package does not complete the entire stage.

## Capability boundary

The static-import extension ([ADR 0030](adr/0030-java-static-import-calls.md)) adds explicit and wildcard imports for unqualified calls to accessible static methods in other ready sources in the same repository. Member names conservatively suppress import fallback, including arity mismatches; explicit imports suppress wildcard fallback even for missing owners. `this`/`super` calls never use imports. Results use `receiver="import static"` and original target symbols/lines, preserving overload/version ambiguity. Private/non-static methods, inaccessible imported types/methods, external dependencies, static-imported nested types/fields, and complete access/type semantics remain excluded. Incomplete member lookup suppresses import fallback.

The static-factory extension ([ADR 0036](adr/0036-bounded-java-static-factory-var-receivers.md)) infers an ordinary method-local `var` only from a complete `Type.factory(...)` initializer when accessible repository-local static candidates agree on one resolvable repository-local return qualified name. The binding begins after its declaration and keeps existing lexical shadowing. Missing, inaccessible, non-static, private, external-return or disagreeing candidates leave the local unknown.

| Area | V1 behavior | Deliberate limit |
| --- | --- | --- |
| Source structure | Top-level types, conventional fields/methods, exact chunks and lines | No complete AST or nested/generated-type semantics |
| Receivers | Direct types, current-type fields, parameters, lexical locals, constructor-initialized `var`, and uniquely returned type-qualified static factories | No general factory/chained inference, reassignment data flow, generic substitution, or runtime data flow |
| Scoped bodies | Ordinary/if/else/while/try/catch/finally and braced enhanced/classic for/resource try | No general unbraced control flow, switch/pattern/lambda/anonymous/local-type semantics |
| Header bindings | Single classic-for declaration; multiple resource declarations or existing references; enhanced-for and catch parameters | Header calls omitted; annotated/complex/multi-declarator headers excluded; unknown `var`, array elements and union catches shadow instead of guessing |
| Inheritance | Repository-local extends/implements candidates, original target IDs, unqualified/this/super calls, signature-based override suppression, diamond deduplication | No runtime implementation selection; private/constructor/interface-static inheritance excluded; full access/type checking deferred |
| Overloads | Argument-count filtering and varargs for same-file and cross-file calls | Same-arity type overloads stay ambiguous; uncertain generic/comparison expressions do not narrow candidates |
| Safety | Same repository/user/project readiness boundaries, duplicate versions ambiguous, no compiler/service execution | Sources not imported or not ready cannot supply targets |

`resolved` means one candidate within these rules, not a guarantee about Java compilation or runtime dispatch. Full Java semantics, external dependency/build-system integration, and further language coverage are separate future work. Multiline headers are supported; body declarations remain the existing line-oriented single-variable subset. Factory inference excludes chained, cast, conditional, instance, unqualified/static-import, header-binding and reassignment forms.

## Bounds

Existing limits remain: 200 symbols, 500 same-file calls, 100 related ready sources, 20 MiB related text, 400 related types, and 500 each for type relationships, related methods, and cross-file calls. A lookup additionally stops after 256 inheritance states; cycles and budget exhaustion set `truncated=true`. Omitted targets cannot leave dangling response edges. Diamonds and duplicate immutable versions are deduplicated by symbol ID, not by type name.

## Unified acceptance

Use the existing backend virtual environment; no GitHub/LLM token, frontend, or database migration is required. Tests use isolated SQLite and fixtures, not real-provider or native PostgreSQL acceptance.

```powershell
# backend/
.\.venv\Scripts\python.exe -m pytest tests/test_java_static_imports.py tests/test_java_v1.py tests/test_java_structure.py tests/test_parsing.py
.\.venv\Scripts\python.exe -m pytest
# repository root
git diff --check
```

Expected results: all tests pass, exact/stable target IDs and lines, lexical exit restoration, no header leakage into catch/finally, preserved ambiguity, cycle/budget termination, repository isolation, and no tracked secrets/dependencies/build output. The integrated API fixture covers resource try → classic for → inherited method → arity selection in one upload/parse/query flow. Run this acceptance after the implementation package is complete, then fix/recheck any failures; do not use individual feature tests to imply package completion.

Decision: [ADR 0029](adr/0029-java-analysis-v1.md).

## Acceptance record — 2026-10-21

Agent-executed after the implementation package and final review corrections: 106 focused tests and 254 full-backend tests passed. Whitespace, new documentation links, and tracked secret/dependency/build-output checks passed. One existing Starlette deprecation warning remains. No real GitHub/LLM, native PostgreSQL, or browser acceptance was performed for this backend-only package.

## Static-import extension acceptance — 2026-10-22

The user selected agent execution after receiving the commands, prerequisites, and expected results. The final focused regression passed 127 tests (including 21 static-import cases); the full backend suite passed 275 tests with the existing Starlette deprecation warning. The sandbox run stalled at the HTTP TestClient phase and was stopped; authorized execution outside the sandbox passed. Changed-document links and tracked secret/dependency/build-output checks passed. No real GitHub/LLM, native PostgreSQL, or browser acceptance was performed for this backend-only extension.

## Static-factory receiver extension acceptance — 2026-10-23

The user selected agent execution after receiving the commands, prerequisites, and expected results. The focused Java/parsing regression passed 133 tests; the full backend suite passed 377 tests with the existing Starlette deprecation warning. The sandbox run again stalled without output at the HTTP TestClient phase and was stopped; authorized execution outside the sandbox passed. No migration, real GitHub/LLM, native PostgreSQL, frontend build, or browser acceptance was required for this backend-only, response-shape-preserving extension.
