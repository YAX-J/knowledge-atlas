# ADR 0055: Scoped workspace orchestration modules

Status: Accepted · Date: 2026-10-26

[简体中文](0055-scoped-workspace-orchestration.zh-CN.md)

## Decision

Move import mutations to useSourceImport, candidate extraction/filtering/review to useCandidateReview, and graph reads/detail selection to useProjectGraph. useKnowledgeRetirement owns new retirement writes/audit reads. Keep existing component props/events, API contracts, project navigation, source detail/evidence navigation and evolution orchestration in App. Do not introduce a router or global store.

Modules own request IDs and synchronous context/disposal invalidation, including leaving and returning to the same project/source/time. Imports receive typed refs and narrow callbacks for selection, list/detail refresh and shared mutation guards; importing files never silently triggers extraction. Keep partial folder success and explicit remote operations. Release upload locks on refresh failures and stop issuing additional file writes after disposal; disposal does not cancel a write already sent to the server. App retains its cross-workflow navigation locks.

## Consequences

App changes from 1326 to 971 lines; line count is not a quality score. Shared useLatestRequest/useKnowledgeSearch remain in use. Existing App event regressions, new module lifecycle tests and actual desktop native-API flows protect behavior. Coverage explicitly includes the new modules and retirement component; scoped percentages do not describe the entire application. Repository snapshots, source read/navigation and evolution remain intentional future extraction candidates rather than being moved wholesale in this change.
