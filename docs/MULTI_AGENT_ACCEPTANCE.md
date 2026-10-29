# Multi-agent refactor acceptance

[简体中文](MULTI_AGENT_ACCEPTANCE.zh-CN.md)

Implemented inside the existing Knowledge Atlas project. Actual modules, API, budgets and known runtime boundaries are documented in [MULTI_AGENT](MULTI_AGENT.md); decisions are ADR0064–0065. The user authorized Agent-run verification; no paid provider experiment was performed.

| Check | Observed result |
| --- | --- |
| Full backend, native compilers enabled | 723 passed, 7 opt-in/native-runner skips; app statement coverage 95.19%, above 90% gate |
| Native PostgreSQL 17.10 / pgvector 0.8.7 | 145 passed in an owned temporary schema; upgrade/downgrade/upgrade passed; schema removed; application marker unchanged |
| Frontend coverage suite | 116 tests across 16 files passed; statement 68.66%, line 73.42%; new scoped run composable line coverage 96.61% |
| Frontend production build | Type check and Vite build passed |
| Desktop browser | Empty state, explicit start, source context, review dependency preview, three-candidate human confirmation, free resume, saved run reload, QA/code combined output, citation navigation, focus and scrolling checked |
| Evidence location | QA citation focused the exact `Visit.java` chunk at lines35–46; no rendered alert or horizontal page overflow |
| Application upgrade | Verified backup archive and fresh isolated-schema recovery before0019;24 existing business-table content fingerprints unchanged; new agent_runs empty; readiness passed |
| Compatibility | Ten moved service modules retain identical canonical module objects; legacy prompt/version constants unchanged |
| Frozen experiments | No evaluation asset changed; no invented human grades; cumulative84 model/61 embedding ledger unchanged |
| Delivery checks | Working/staged diff whitespace and changed Markdown links checked; ignored output/dependencies/secrets excluded from the local commit |

Reproduction commands from `backend/`:

```powershell
$env:KA_NATIVE_COMPILERS='1'
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-fail-under=90 --cov-report=term:skip-covered
.\.venv\Scripts\python.exe -m scripts.verify_native
```

From `frontend/`: `npm run test:coverage` and `npm run build`. Native verification requires installed PostgreSQL/pgvector and Java/Node/Go for compiler acceptance. Database scripts read local configuration without printing credentials. Full-suite skips correspond to tests requiring explicit public GitHub permission or the dedicated native runner; native checks are run separately as shown.

Browser verification used `scripts.qa_workspace` on8010, Vite on5180 and task-owned Chrome sessions. Real HTTP, parsing, candidates, review, graph, task persistence and compiler adapters were used, with model/tool-call protocol substitutes. This checks integration, not real model quality. First fixture source extraction quoted a closing brace; it was used only to verify the human checkpoint. The later QA/compiler check used the prepared public evidence `@Column(name = "visit_date")`, verifying exact source focus. Browser sessions, owned service processes and both recorded temporary schemas were closed/removed. No application knowledge was inserted during browser tests. Backups/logs/screenshots remain ignored local output.

Two initial native assertions incorrectly counted fixtures from other committed projects. They were corrected to filter the current project/source, then the final full and native suites passed. No production scope check was removed.

Current limitations are explicit: execution is synchronous, final events are persisted on completion rather than streamed, and expired runs do not provide automatic crash-node recovery or paid retry. API code version selection is supported; the collaboration page currently uses the default immutable selection. Human blind grading, actual private GitHub authorization, Docker and remote CI retain their prior acceptance status. These are not declared complete by this refactor.
