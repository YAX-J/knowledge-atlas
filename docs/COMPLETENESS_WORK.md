# Functional completion work — 2026-10-26

User scope: address the seven functional/research gaps from the completeness review; engineering/deployment work is excluded. Agent runs verification (standing user choice, including tests/build/native/browser/diff checks). Public-only provider budget explicitly authorized: at most 120 answer/extraction/call-analysis requests and 160 embedding requests. Never send private inputs. Public-v2 run1 succeeded: 81 model / 61 embedding attempts; separate public code-call acceptance used 3 model attempts. Cumulative **84 model / 61 embedding**, checked against ignored output/completeness-20261026/provider-budget.json (120/160 caps). Do not reset it.

Implementation checklist:
- [x] Immutable-commit file continuation and local folder import; directory traversal fallback, immutable frontier, hard bounds, moved branches and multi-page rename/deletion reconciliation regressions passed.
- [x] Audited aliases, entity identity merge and time-aware canonical evidence/edges. Original-owner vectors are projected at query time; historical queries cannot absorb future merge text.
- [x] Audited withdrawal/reactivation preserving closed historical intervals; group split/merge evolution and reversal of an independent linear replacement.
- [x] Persistent scoped conversations, idempotent turns, separate execution fencing and bounded grounded follow-ups.
- [x] Import-aware candidates and explicit native Java/TypeScript/Go same-package analysis; actual 3 compiler checks, syntax/type diagnostics, escaping/duplicate-path refusal and sanitized process-failure regressions passed.
- [x] Real overview/top navigation/contextual search, lifecycle/identity/conversation UI; unknown turn IDs survive navigation/reload in tab storage and explicit retries reuse them. Workbench error retries and write-time search locks verified.
- [x] New 10-source/20-question pinned public corpus and real online QA comparison; 81 model/61 embedding calls. RRF Recall@5 85.9375%, vector 79.6875%, BM25 73.4375%, hybrid 39.0625%; small paired RRF-v-vector CI includes zero. 80 blank human review rows. No human scores fabricated.
- [x] Final full backend: **704 passed, 7 skipped**, app coverage **94.88%** (90% gate), with KA_NATIVE_COMPILERS=1; no real providers in tests.
- [x] Final native PostgreSQL 17.10 / pgvector 0.8.7: **129 tests passed**, upgrade/downgrade/upgrade in isolated schema; removed own schema and verified application marker unchanged.
- [x] Final frontend: **93 tests passed**, type checks and build passed (1663 modules). Configured coverage: 71.94% statements, 62.91% branches, 50% functions, 76.93% lines.
- [x] Desktop Chrome at 1440×1100: real counts/navigation, Ctrl+K focus, header/query sync, source upload→parse→stub extraction→batch review→graph, alias audit, withdrawal/reactivation, persistent reload/follow-up and blank offline blind review. Document width 1440; graph/list panels scroll; no page errors.
- [x] Bilingual current docs, four ADR pairs, seven repository skills and research charts/report synchronized; git diff --check passed.
- [x] Final staged review: 150 intended files, no dependency/build/private/config artifacts or credential patterns; staged public corpus exact-byte fingerprint matches the frozen protocol. Local commit contains this record; its hash is reported in the task response.

External acceptance: private repository address/token setup and real reviewers requested asynchronously; never fabricate private acceptance or human scores. Full compiler/runtime semantics cannot be inferred from syntax/model output; report exact supported contexts and remaining boundaries. Do not modify real application schema without a recoverable backup and concrete review.

Main application schema remains **20261026_0017**; no business migration or deployment was performed. Before using the new code with the application database, preserve a recoverable backup, run `.\.venv\Scripts\python.exe -m alembic upgrade head` from backend (expected 20261026_0018), then restart API/worker/frontend. Downgrade removes newly recorded identity/history/conversation data and is not business undo.

Verification commands run by Agent: `KA_NATIVE_COMPILERS=1` plus `.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term --cov-fail-under=90`; `.\.venv\Scripts\python.exe -m scripts.verify_native`; `npm run test:coverage`; `npm run build`; independent agent-browser walkthrough; `git diff --check`.

All owned verification processes/browser closed. Windows interruption left the browser schema behind; cleanup verified its unique synthetic project, qa-note.md and the known temporary entity UUID before dropping only ka_functional_3aa9edd54b6c43c082dc5c4e9a910685. Ports 8010/5180 no longer listen. Public research schemas were removed by their runners. Application marker remains 0017. Initial public-v2 result dir records a zero-provider preflight failure (ConfigParser percent escaping); corrected successful dir is evaluation/results/2026-10-26-public-v2-run1. Do not overwrite either directory.

External acceptance still open: no configured private token/repository supplied and no real human grades. Public-v2's ten files/twenty agent-authored questions and one real call positive do not establish representative full-repository accuracy. Native compiler support remains the explicitly documented static source contexts; complete arbitrary-language builds/runtime dispatch are not claimed.
