# ADR 0062 Restorable workspace composition

[简体中文](0062-restorable-workspace-composition.zh-CN.md)

- Status: Accepted
- Date: 2026-10-29

## Decision

Extend ADR 0055 with hash URL navigation for project/source/entity/relationship/time/conversation and graph task sections. No server rewrite or state-store dependency is required. URLs contain identifiers and timestamps, not question/source text. Restore through scoped API reads, show invalid-link errors with explicit retry, fence delayed restoration on intentional navigation and refuse context changes during writes. Historical conversation reads never resend questions.

Split graph tasks into relations/search/identity/evolution/retirement while preserving selected knowledge/time. Extract evidence navigation, snapshot lists/files/import and evolution/governance/comparison into three lifecycle-scoped composables. App connects shared context and mutation locks; presentation components keep props/events. Request generations and disposal preserve late-response refusal.

## Consequences

Refresh and browser history can restore useful work without replaying mutations. Search drafts, analysis strategy/version choices and unsaved forms are not persisted. Hash IDs still require backend authorization. This supersedes the earlier recommendation to keep all page orchestration in App once routing became justified.
