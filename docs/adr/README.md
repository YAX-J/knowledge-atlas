# Architecture Decision Records

[简体中文](README.zh-CN.md)

Architecture Decision Records capture durable choices that affect multiple components, data semantics, security, deployment, or future implementation work.

## When to add an ADR

Add an ADR when a decision changes one or more of the following:

- Source-of-truth or cross-database synchronization rules.
- Knowledge entity, relationship, evidence, or temporal semantics.
- Public API conventions.
- Major framework, storage, queue, model-provider, or deployment choices.
- Security boundaries or handling of private developer data.

Small refactors and local component choices do not require an ADR unless they constrain future work.

## File naming

Use a four-digit sequence and a short lowercase slug:

```text
0001-postgresql-source-of-truth.md
0002-native-svg-for-prototype-graph.md
```

Do not reuse a number. Superseded records remain in the repository. Chinese companions use the same sequence and a `.zh-CN.md` suffix; they do not allocate another number.

## Status values

- `Proposed`: under discussion.
- `Accepted`: current decision.
- `Superseded`: replaced by a newer ADR.
- `Rejected`: considered but not adopted.

## Template

```markdown
# ADR NNNN Decision title

- Status: Proposed
- Date: YYYY-MM-DD

## Context

What problem or constraint requires a decision?

## Decision

What is being decided?

## Consequences

What becomes easier, harder, required, or intentionally unsupported?

## Alternatives considered

Which credible alternatives were evaluated and why were they not selected?
```

Update related architecture, API, knowledge-model, and setup documents when an ADR changes their assumptions.

## Existing decisions

- [ADR 0001: PostgreSQL as the source of truth](0001-postgresql-source-of-truth.md) (superseded by ADR 0005)
- [ADR 0002: Native SVG for the prototype graph](0002-native-svg-for-prototype-graph.md)
- [ADR 0003: Persist Markdown chunks and run parsing explicitly](0003-markdown-parsing-execution.md)
- [ADR 0004: Database-backed parsing worker with execution leases](0004-database-backed-parsing-worker.md)
- [ADR 0005: Use PostgreSQL only and defer Neo4j](0005-postgresql-only-storage.md)
- [ADR 0006: Explicit DeepSeek candidates with evidence-gated review](0006-deepseek-candidate-review.md)
- [ADR 0007: Promote confirmed candidates into the PostgreSQL graph](0007-confirmed-postgresql-graph.md)
- [ADR 0008: Evidence-backed project keyword search](0008-project-keyword-search.md)
- [ADR 0009: Build the formal-knowledge semantic index explicitly](0009-explicit-semantic-index.md)
- [ADR 0010: Explainable hybrid retrieval with one-hop graph signals](0010-explainable-hybrid-graph-retrieval.md)
- [ADR 0011: Synchronous evidence-grounded questions with validated citations](0011-synchronous-evidence-grounded-questions.md)
- [ADR 0012: Bounded Java source ingestion with line-preserving chunks](0012-bounded-java-source-ingestion.md)
- [ADR 0013: Derive bounded Java source structure outside the formal graph](0013-derived-java-source-structure.md)
- [ADR 0014: Resolve bounded cross-file Java type relationships on demand](0014-bounded-cross-file-java-types.md)
- [ADR 0015: Identify local-folder source repositories within a project](0015-local-folder-repository-identity.md)
- [ADR 0016: Normalize GitHub remote identity before repository import](0016-normalized-github-remote-identity.md)
- [ADR 0017: Resolve bounded cross-file Java method calls on demand](0017-bounded-cross-file-java-method-calls.md)
- [ADR 0018: Import bounded GitHub repository snapshots explicitly](0018-bounded-github-snapshot-import.md)
- [ADR 0019: Persist incremental GitHub commit snapshots](0019-incremental-github-commit-snapshots.md)
- [ADR 0020: Derive immutable GitHub evidence links from snapshots](0020-derived-immutable-github-evidence-links.md)
- [ADR 0021: Import bounded GitHub work items as immutable source versions](0021-versioned-github-work-items.md)
- [ADR 0022: Resolve bounded Java calls through declared method receivers](0022-bounded-java-declared-receiver-calls.md)
- [ADR 0023: Version bounded GitHub Pull Request review activity independently](0023-versioned-github-pull-reviews.md)
- [ADR 0024: Snapshot bounded GitHub review thread state through GraphQL](0024-bounded-github-review-thread-state.md)
- [ADR 0025: Infer bounded Java var receivers from constructor initializers](0025-constructor-initialized-java-var-receivers.md)
- [ADR 0026: Resolve Java local receivers within bounded lexical blocks](0026-scoped-java-local-receivers.md)
- [ADR 0027: Resolve Java receivers through bounded enhanced-for elements](0027-enhanced-for-java-receivers.md)
- [ADR 0028: Resolve Java calls within bounded exception scopes](0028-java-exception-scope-receivers.md)
- [ADR 0029: Package bounded repository-local Java analysis V1](0029-java-analysis-v1.md)
- [ADR 0030: Resolve bounded repository-local Java static-import calls](0030-java-static-import-calls.md)
- [ADR 0031: Recover incomplete GitHub snapshots with typed source reuse](0031-recoverable-typed-github-snapshots.md)
- [ADR 0032: Search bounded Java source symbols and open original chunks](0032-bounded-code-symbol-search.md)
- [ADR 0033: Import saved commit messages as evidence sources](0033-saved-commit-evidence-sources.md)
- [ADR 0034: Read saved snapshot file provenance](0034-snapshot-file-provenance.md)
- [ADR 0035: Navigate evidence to exact original source chunks](0035-exact-evidence-source-navigation.md)
- [ADR 0036: Infer bounded Java `var` receivers from static factory calls](0036-bounded-java-static-factory-var-receivers.md)
- [ADR 0037: Resolve unqualified Java factory receivers](0037-unqualified-java-factory-receivers.md)
- [ADR 0038: Infer Java factory receivers in loop and resource headers](0038-java-header-factory-receivers.md)
- [ADR 0039: Review cross-source knowledge evolution explicitly](0039-reviewed-knowledge-evolution.md)
- [ADR 0040: Parse multiple code languages without changing knowledge authority](0040-multilanguage-source-parsing.md)
- [ADR 0041: Run bounded multi-language cross-file call analysis through an Agent](0041-bounded-multilanguage-agent-call-analysis.md)
- [ADR 0042: Replay curated synthetic evaluation projects through review services](0042-reproducible-curated-evaluation-projects.md)
- [ADR 0043: Bounded read-only repository tools](0043-bounded-read-only-tool-agent.md)
- [ADR 0044: Add a bounded offline lexical baseline](0044-bounded-offline-bm25-search.md)

- [0045: Opt-in rank fusion and online evidence allocation](0045-opt-in-rank-fusion.md)

- [0046: Atomic batch review and read-only index status](0046-atomic-batch-review-index-status.md)

- [0047: Filtered discovery and passage attribution](0047-filtered-discovery-evidence-attribution.md)

- [0048: Relation review dependency visibility](0048-review-endpoint-visibility.md)

- [0049: Filtered source discovery and recoverable pagination](0049-source-discovery-filters.md)

- [0050: Durable index rebuilds and uncertain outcomes](0050-durable-index-rebuilds.md)

- [0051: Optional source-aware lexical retrieval](0051-source-aware-lexical-retrieval.md)

- [0052: Verified native backup and guarded restore](0052-verified-native-backups.md)

- [ADR 0053: Projected source lists and batched search evidence](0053-batched-read-paths.md)

- [ADR 0054: Audited knowledge retirement](0054-audited-knowledge-retirement.md)

- [ADR 0055: Scoped workspace orchestration](0055-scoped-workspace-orchestration.md)

- [ADR 0056: Audited identities and historical validity](0056-audited-identities-and-validity.md)

- [ADR 0057: Grounded persistent conversations and measured defaults](0057-grounded-persistent-conversations.md)

- [ADR 0058: Resumable immutable GitHub manifests](0058-resumable-immutable-github-manifests.md)

- [ADR 0059: Explicit native static declaration analysis](0059-explicit-native-static-call-analysis.md)

- [ADR 0060: Schema-aware readiness](0060-schema-aware-readiness.md)

- [ADR 0061: Immutable analysis context](0061-immutable-analysis-context.md)

- [ADR 0062: Restorable workspace composition](0062-restorable-workspace-composition.md)

- [ADR 0063: Measured index planning](0063-measured-index-planning.md)

- [ADR 0064: Scoped agent modules](0064-scoped-agent-modules.md)

- [ADR 0065: Durable reviewed workflows](0065-durable-reviewed-workflows.md)

- [ADR 0066: Batched global lexical retrieval](0066-batched-global-lexical-retrieval.md)

- [ADR 0067: Durable agent progress](0067-durable-agent-progress.md)

- [ADR 0068: Explicit workflow scope](0068-explicit-workflow-scope.md)

- [0069 — Claim-level answer evidence](0069-answer-claim-evidence.md)
