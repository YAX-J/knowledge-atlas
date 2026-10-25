# Search state optimization — 2026-10-25

[简体中文](SEARCH_STATE_OPTIMIZATION_20261025.zh-CN.md)

Search, retry, index status and explicit index rebuild orchestration now live in `frontend/src/composables/useKnowledgeSearch.ts`. App retains project selection, graph navigation and evidence navigation. There is no API, database or dependency change.

The module invalidates reads synchronously when the project or effective time changes, including leaving and returning to the same context. Retry retains the submitted query, type and retrieval mode. A per-project in-flight set guards index rebuilds throughout the current App instance: clearing visible search state does not cancel a server write or unlock another rebuild. Old completions cannot restore notices, errors or automatic searches. A normal successful update refreshes index status and retries only the existing vector/hybrid/rrf search; BM25 results remain visible without another lexical request.

## Verification

The agent executed the checks under the user's standing authorization; all external provider outputs were stubbed.

- `npm test -- tests/knowledgeSearchState.test.ts tests/appRequests.test.ts`: 19 passed, including context round trips, clear, retry, old failures, rebuild guards and disposal.
- `npm run test:coverage`: 52 tests passed across 8 files. The new module has 100% statement and 97.05% branch coverage. The configured aggregate is 62% statements / 58.6% branches, and now includes this module alongside the existing selected frontend files. The expanded denominator means it is not directly comparable with the prior aggregate or whole-application coverage.
- `npm run build`: strict TypeScript checks and production build passed.
- System Chrome at 1440 × 1100 against the real local API and an isolated native PostgreSQL fixture: BM25 keyboard submit returned two results; delaying an index response then clearing search left the update button disabled and recorded one rebuild request. Releasing the response restored the button without restoring results or notices. A normal rebuild retained two BM25 results and produced no extra search request.
- Search-region axe: 0 violations, 0 incomplete checks. No horizontal overflow or browser errors observed.
- `git diff --check`, changed Markdown local links and tracked-file hygiene checked before commit.

The temporary schema physically owned every metadata table before fixture writes; the fixture project was absent from `public`. The named browser, dedicated API/Vite processes and validated schema were cleaned up. Temporary scripts/logs remain ignored under `output/search-state-20261025/`.

Backend code is unchanged; full backend tests and the separate native migration/contention suite were not rerun in this turn. Browser acceptance used real local persistence and stubbed embeddings, not real provider quality. Rebuild guards apply to one mounted App instance; cross-tab/server deduplication and server cancellation are outside this change.
