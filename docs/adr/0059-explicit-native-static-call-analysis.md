# ADR 0059 Explicit native static declaration analysis

[简体中文](0059-explicit-native-static-call-analysis.zh-CN.md)

- Status: Accepted
- Date: 2026-10-26

## Decision

Extend ADR 0041/0043 with strategy=semantic using trusted helpers: javac parse/analyze with -proc:none/no emit/JDK17 release, virtual TypeScript checker without config/plugins/emit, and Go parser/types for same-package source. No user program, build script or imported module executes. Map compiler declarations to immutable path/line evidence with stable derived UUIDs, including declarations omitted by bounded outline candidates. Report syntax/type-context diagnostics and unresolved calls. Keep 30s subprocess/output bounds and reject duplicate path versions.

## Consequences and alternatives

Compiler resolution is static declaration identity, not runtime dispatch or full project semantics. Dependencies/build classpaths are not inferred or installed. C/C++/C# retain syntax/Agent support; unavailable SDK returns an explicit error. Native engines make no provider request.
