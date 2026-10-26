# Optimization 4–6 acceptance — 2026-10-26

[简体中文](OPTIMIZATION_456_20261026.zh-CN.md)

The user requested, in order: measure and improve growing-data read performance; auditable correction/retirement; progressively extract frontend orchestration. The previously authorized agent executes all verification, without real model, embedding or GitHub requests. No thesis/defense work is included.

## 4. Measured reads

Native PostgreSQL 17.10 / pgvector 0.8.7, same synthetic 100-source/100-entity/2000-parsing-task fixture, three fresh-session samples per operation. Source content is projected out and only one latest task per source is returned; evidence and Git provenance are batch-read for every search mode. See [complete raw samples and limits](../evaluation/performance/2026-10-26-read-paths/README.md).

| Operation | Queries before → after | Median ms before → after | Python allocation peak bytes before → after |
| --- | --- | --- | --- |
| Sources page 100 | 8 → 8 | 182.924 → 46.385 | 27,433,069 → 868,824 |
| Keyword top 50 | 253 → 8 | 407.964 → 45.874 | 1,020,038 → 734,609 |
| BM25 top 50 | 255 → 10 | 423.279 → 66.280 | 1,269,886 → 978,869 |

All 11 normalized output fingerprints match. Top-1 timing did not consistently improve. This is a local service/serialization and Python-allocation diagnostic, not HTTP/p95/RSS/database-memory or large-production-capacity evidence. Ranking and existing scan limits are unchanged; no provider timing or new answer-quality conclusion.

## 5. Audited correction and retirement

Explicitly retire a current active entity or relationship for correction/obsolescence, with a reason and second UI confirmation. In one project-locked transaction, close valid_to at server time and store immutable before/after snapshots; keep original candidates, review events, evidence and vectors. Current retrieval/questions/graph exclude retired records, incident edges follow endpoint visibility, and prior-time details/evidence remain readable. Pending evolution revalidates closed endpoints. Same submission UUID is idempotent; changed input/other retirement conflicts. Unknown outcomes never auto-resend; explicit same-input retry retains its UUID in the mounted workspace. Audits are scoped and paginated.

Migration `20261026_0017` is applied to the application database after a snapshot backup; all pre-existing business table content fingerprints remained unchanged. The final clean backup and restored schema each contain **19 tables**, with complete schema/content fingerprints matching. Temporary targets were removed. Final private backup: ignored `output/optimization-456-20261026/verified-backup-0017/`. Earlier backups captured the concurrent private QA schema; the schema-only restore command correctly rejected that multi-schema snapshot. Only the post-cleanup 19-table backup is the final application schema-recovery acceptance. Full fresh-database restore still requires privileges unavailable to the current role; this turn does not claim it passed.

Correction means removing a mistaken claim from current use; replacement content must undergo normal review. No merge, reversal of original confirmation, reactivation, backdating, scheduled retirement or physical deletion. Hard archive still hides history and is not used here. Downgrade removes audits without reopening intervals, so preserve a verified backup before downgrade.

## 6. Frontend ownership

`useSourceImport`, `useCandidateReview` and `useProjectGraph` own import writes, review workflows and graph reads respectively; `useKnowledgeRetirement` owns the new lifecycle workflow. Preserve component events, partial folder success, explicit remote operations, navigation locks and synchronous project/source/time/disposal invalidation. Upload refresh failures release locks; disposal does not cancel already-sent server work. App retains navigation, source evidence/snapshot and evolution orchestration. App: **1326 → 971 lines**, without a router/store or claim that line count measures quality.

## Verification actually executed

- Focused backend: `python -m pytest tests/test_read_performance.py tests/test_retirement.py tests/test_migrations.py tests/test_graph.py tests/test_search.py tests/test_retrieval_optimization.py tests/test_source_filters.py --tb=short --show-capture=no`: **62 passed**.
- Full backend: `python -m pytest --cov=app --cov-fail-under=90 --cov-report=term --cov-report=xml:../output/backend-coverage.xml --tb=short --show-capture=no`: **672 passed, 7 conditional skips; 94.76% statement coverage**. Existing Starlette/httpx deprecation warning remains.
- `python -m scripts.verify_native`: migration upgrade/downgrade/upgrade, independent-session competing/repeated retirement, read-count, history/scope/transaction and existing workflow tests passed. Test fixture queries were made project-scoped and read-count assertions exclude transaction savepoints. Disposable schema removed, application migration marker unchanged during the isolated suite.
- Frontend focused orchestration/lifecycle/App regressions, then `npm run test:coverage`: **84 passed in 10 files**, configured statements **74.97%**, branches **66.56%**. Denominator now includes new modules/component, not the whole application. `npm run build` passed after the final production changes.
- Chrome 1440 × 1100 with real local API/native PostgreSQL and synthetic provider outputs: upload → parse → extract → manually confirm → graph; retire entity and relationship, verify current exclusion, audit reason/snapshots and historical exact-line evidence. History is read-only; keyboard focus visible, no horizontal page overflow or browser errors observed. New retirement region axe: **0 violations, 0 incomplete**, not a whole-app certification. Screenshot visually inspected at ignored `output/optimization-456-20261026/retirement-history.png`.
- Named browser, recorded QA API/Vite processes and private fixture schema cleaned; test project absent from public, dedicated ports released. Existing user services were preserved.
- Before committing: `git diff --check`, modified Markdown links/bilingual pairs, staged diff and generated-file/credential hygiene checks. Private backups, browser outputs, environment files and dependencies remain untracked/ignored.
