# Repository-local Java analysis V1

[简体中文](JAVA_ANALYSIS_V1.zh-CN.md)

V1 is a bounded, read-only source outline and call-candidate analysis, not a Java compiler or runtime call graph. Results come from immutable uploaded/parsed sources, retain original lines and deterministic symbol IDs, and never bypass knowledge review or enter the formal graph automatically. Stage 4 also contains separate GitHub and evaluation work; this package does not complete the entire stage.

## Capability boundary

| Area | V1 behavior | Deliberate limit |
| --- | --- | --- |
| Source structure | Top-level types, conventional fields/methods, exact chunks and lines | No complete AST or nested/generated-type semantics |
| Receivers | Direct types, current-type fields, parameters, lexical locals, constructor-initialized `var` | No factory/chained inference, generic substitution, or runtime data flow |
| Scoped bodies | Ordinary/if/else/while/try/catch/finally and braced enhanced/classic for/resource try | No general unbraced control flow, switch/pattern/lambda/anonymous/local-type semantics |
| Header bindings | Single classic-for declaration; multiple resource declarations or existing references; enhanced-for and catch parameters | Header calls omitted; annotated/complex/multi-declarator headers excluded; unknown `var`, array elements and union catches shadow instead of guessing |
| Inheritance | Repository-local extends/implements candidates, original target IDs, unqualified/this/super calls, signature-based override suppression, diamond deduplication | No runtime implementation selection; private/constructor/interface-static inheritance excluded; full access/type checking deferred |
| Overloads | Argument-count filtering and varargs for same-file and cross-file calls | Same-arity type overloads stay ambiguous; uncertain generic/comparison expressions do not narrow candidates |
| Safety | Same repository/user/project readiness boundaries, duplicate versions ambiguous, no compiler/service execution | Sources not imported or not ready cannot supply targets |

`resolved` means one candidate within these rules, not a guarantee about Java compilation or runtime dispatch. Full Java semantics, external dependency/build-system integration, and further language coverage are separate future work. Multiline headers are supported; body declarations remain the existing line-oriented single-variable subset.

## Bounds

Existing limits remain: 200 symbols, 500 same-file calls, 100 related ready sources, 20 MiB related text, 400 related types, and 500 each for type relationships, related methods, and cross-file calls. A lookup additionally stops after 256 inheritance states; cycles and budget exhaustion set `truncated=true`. Omitted targets cannot leave dangling response edges. Diamonds and duplicate immutable versions are deduplicated by symbol ID, not by type name.

## Unified acceptance

Use the existing backend virtual environment; no GitHub/LLM token, frontend, or database migration is required. Tests use isolated SQLite and fixtures, not real-provider or native PostgreSQL acceptance.

```powershell
# backend/
.\.venv\Scripts\python.exe -m pytest tests/test_java_v1.py tests/test_java_structure.py tests/test_parsing.py
.\.venv\Scripts\python.exe -m pytest
# repository root
git diff --check
```

Expected results: all tests pass, exact/stable target IDs and lines, lexical exit restoration, no header leakage into catch/finally, preserved ambiguity, cycle/budget termination, repository isolation, and no tracked secrets/dependencies/build output. The integrated API fixture covers resource try → classic for → inherited method → arity selection in one upload/parse/query flow. Run this acceptance after the implementation package is complete, then fix/recheck any failures; do not use individual feature tests to imply package completion.

Decision: [ADR 0029](adr/0029-java-analysis-v1.md).

## Acceptance record — 2026-10-21

Agent-executed after the implementation package and final review corrections: 106 focused tests and 254 full-backend tests passed. Whitespace, new documentation links, and tracked secret/dependency/build-output checks passed. One existing Starlette deprecation warning remains. No real GitHub/LLM, native PostgreSQL, or browser acceptance was performed for this backend-only package.
