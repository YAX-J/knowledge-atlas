# Retrieval and workflow optimization acceptance (2026-10-25)

[简体中文](OPTIMIZATION_ACCEPTANCE_20261025.zh-CN.md)

The user requested optimization in this order: retrieval/questions, ingestion/review experience, knowledge maintenance, and code structure. They explicitly selected Agent-run verification. No thesis or defense preparation, real provider requests, or GitHub synchronization was performed.

## Delivered behavior

1. Optional BM25/vector RRF search and hybrid/rrf/vector/bm25 question selection, preserving defaults. Online questions deduplicate exact source/chunk/line/quote keys, allocate evidence round-robin and expose selected/duplicate counts. See [ADR 0045](adr/0045-opt-in-rank-fusion.md).
2. Whole-source live pending/confirmed/rejected totals, next-step guidance and graph navigation. Counts are independent of pagination; parsing completion is distinguished from knowledge availability.
3. Duplicate detection now covers later summary groups under the same name/type. Missing evidence and duplicates precede orphan findings; entity names/summaries and evidence navigation work outside the visible canvas. Inspection remains read-only.
4. Shared latest-request state for search/questions preserves project/time scoping, clear and disposal behavior. App regressions cover project switching, stopping the wait and retry mode. Question text contrast is improved.

## Actual verification

- Initial backend focus: 97 passed, 1 failed because an existing test expected the whole extraction response to remain identical after review. Updated assertions separately verify task idempotency and live totals; targeted reruns passed.
- Full backend: `.\.venv\Scripts\python.exe -m pytest --cov=app --cov-fail-under=90 --cov-report=term --cov-report=xml:../output/backend-coverage.xml --tb=short --show-capture=no`: 618 passed, 5 conditional skips; application statement coverage 94.37%. Existing Starlette/httpx deprecation warning remains.
- Native PostgreSQL 17.10 / pgvector 0.8.7: `python -m scripts.verify_native` passed, including the new retrieval and maintenance tests. A first-run fixture query lacked project filtering; after correcting it the native suite passed. Disposable schema removed; application migration marker unchanged.
- Frontend `npm run test:coverage`: 24 passed, 49.71% within the existing client/four-component scope. New composable/App/governance tests ran but were not added to that historical coverage denominator. Final `npm run build` passed.
- System Chrome 1440×1100: existing public synthetic project, source review totals, graph navigation, governance inspection, RRF selection/Enter/error/retry, and real BM25 no-evidence refusal. QA provider endpoints were pinned to an unavailable loopback address. Successful RRF ranking is covered by native tests with stubbed providers, not browser real-provider acceptance.
- Delayed the real local no-evidence response by 2.5 seconds in the page: stopping the wait kept the answer empty and loading false after the late reply. Restored fetch and resubmitted successfully. Visible 2px keyboard focus and no horizontal page overflow. Question region axe-core 4.12.1: zero violations/incomplete checks, not a whole-site certification.
- `git diff --check`, added documentation links and tracked-file inspection passed; no secrets, dependencies or build outputs are tracked. Closed the named browser and dedicated QA API/frontend processes; ports 8001/5174 released.

## Remaining boundaries

No new real-model quality or independent retrieval-effectiveness conclusion. RRF remains opt-in and preserves historical results. Entity merging, undo, batch review, automatic index maintenance and further natural-language/code-identifier recall improvements remain future work. Stopping the wait does not cancel an already-issued server-side model request.
