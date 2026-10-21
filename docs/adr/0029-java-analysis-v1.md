# ADR 0029: Package bounded repository-local Java analysis V1

[简体中文](0029-java-analysis-v1.zh-CN.md)

- Status: Accepted
- Date: 2026-10-21

## Context

The user requested completing the current Java analysis feature as one package before unified testing. Repeated small lexical extensions left classic-for/resource scopes and useful inheritance/overload candidates disconnected. A complete Java compiler remains outside this repository's bounded source-analysis architecture.

## Decision

- Package the [V1 capability and acceptance boundary](../JAVA_ANALYSIS_V1.md) rather than imply complete Java semantics. Retain the existing API shapes, repository/readiness/byte/result limits, chunks, persistence, and reviewed-knowledge boundary; add no compiler dependency, service, migration, or frontend requirement.
- Reuse lexical bindings for braced classic-for and resource-try bodies. Accept a single classic-for declaration, multiple resource declarations or existing references; infer constructor-only `var`. Header calls stay omitted, bindings end at body exit, and unknown bindings suppress fallback.
- Resolve inherited candidates across repository-local extends/implements edges using original method symbols, normalized raw parameter signatures for override suppression, and diamond deduplication. Include inherited unqualified/this/super calls. Do not inherit constructors, private methods, or interface static methods; package-private methods cannot cross package paths. Preserve ambiguous source versions and candidate branches.
- Filter both same-file and cross-file calls by known argument count, including varargs. Keep literal markers while masking to distinguish an empty string from no arguments. Unknown expression grammar preserves candidates; same-count type overloads remain ambiguous, and runtime dispatch is not inferred.
- Limit each inheritance lookup to 256 visited states. Cycles or budget exhaustion report truncation. Keep deterministic target ordering and discard dangling edges under output limits.
- This supplements ADRs 0017 and 0022–0028 only for the V1 subset. Full AST/classpath/type/access checks, generic substitution, advanced language constructs, factory inference, and runtime behavior remain separate future work. Stage 4 is not automatically complete.

## Consequences

The existing outline can follow common loop/resource collaborators to inherited declarations with fewer obviously incompatible overloads. The package has one integrated API acceptance path and unified backend regression, rather than treating each tiny syntax addition as a finished feature. Results remain bounded static candidates, never authoritative graph facts or compiler-certified calls.
