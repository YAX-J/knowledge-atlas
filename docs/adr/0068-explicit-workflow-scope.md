# ADR 0068 Explicit collaboration scope and saved scope reads

[简体中文](0068-explicit-workflow-scope.zh-CN.md)

- Status: Accepted
- Date: 2026-10-30
- Extends ADR 0064–0065/0067; reuses immutable context selection from ADR 0061. No schema migration; head remains `20261029_0019`.

## Decision

Expose the existing retrieval_mode, valid_at, snapshot_id and version_ids workflow parameters in the collaboration page. Keep BM25 as the default; vector/hybrid/RRF still require configured semantic retrieval. Convert optional datetime-local input using the displayed browser timezone into an aware UTC instant. A historical question clears/disables current-code analysis and omits code/source/version parameters; switching to knowledge preparation clears history time.

`useCodeContextSelection` reuses the existing read-only analysis-contexts API and useLatestRequest fencing. Project/source/enable changes invalidate pending reads, clear old choices and suppress late results across round trips/disposal. Loading, failed or invalid metadata blocks paid submission; retry performs only GET. Show the server's preferred snapshot or local overrides, never mix them, validate membership and the 99-override limit, and disclose metadata truncation. The main source remains its opened immutable version; unspecified related local files are selected at execution time, not frozen at metadata-read time. The backend remains authoritative for project/repository/time/byte/source scope before compiler/provider work.

Preview the new draft separately from saved results. Extend start/list/read/resume responses with an allowlisted `scope` projection of the existing stored request: retrieval_mode, valid_at, include_code_analysis, code_strategy, snapshot_id, version_ids. Question fields are null for knowledge preparation; unused code fields are null/empty. Do not expose the raw request, source hash, prompt or credentials. Client types tolerate absent/null scope from old servers. Saved scope is read-only and does not hydrate a new draft or replay provider calls. Existing submission UUID/session-storage behavior remains.

## Consequences and limits

Users can choose and later inspect the requested scope instead of receiving an implicit BM25/default-code request. Actual code analysis context is still returned independently in code results. Version metadata is bounded and may be stale by submission; explicit invalid choices are rejected, with no silent paid fallback. Draft question/time/options are not added to URLs or automatically restored after reload. This does not add authentication, arbitrary planning, automatic node continuation, source synchronization or a provider-quality experiment.

## Verification

The user's Agent-execution choice was retained. On 2026-10-30, focused frontend 28/backend 31 tests passed; final full frontend regression passed 127 tests across 17 files (configured statements 69.54%, lines 74.21%; context-selection composable lines 100%). Production type checking/build passed. Full backend with `KA_NATIVE_COMPILERS=1`: 752 passed, 8 opt-in cases skipped, statement coverage 95.26%, exceeding the 90% gate. PostgreSQL 17.10 / pgvector 0.8.7: 175 passed in the owned schema; migration roundtrip/cleanup passed and the application marker was unchanged.

Desktop Chrome used a named agent-browser session and dedicated 8012/5182 ports. An ignored wrapper seeded normal imported/parsed synthetic TypeScript versions and synthetic snapshot manifests only after verifying ownership of every table in qa_workspace's disposable schema. Browser checks covered explicit older local version, older fixed snapshot and actual returned context, separate draft/saved scopes, read failure blocking submit and read-only retry, historical RRF, timezone conversion (Asia/Shanghai 2010-01-01 10:30 → 02:30Z), current-code omission, refresh recovery, keyboard focus and long-path wrapping without horizontal overflow. Native datetime input used its value setter/input events because the CLI fill command did not populate it; no date-picker popup acceptance is claimed. Provider calls were local substitutes; snapshot SHAs were synthetic, not a new GitHub acceptance result. Dedicated browser/services closed and the browser schema was removed; output remains ignored.

Final source-only knowledge preparation hides empty draft/saved scope regions; its regression and desktop local-stub review-entry check passed. Both owned browser schemas and dedicated services were cleaned up. No real-provider calls, human grades, frozen evaluation changes or new migration. Whitespace/local links/staged artifacts are checked before local commit.
