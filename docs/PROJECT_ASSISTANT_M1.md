# Project assistant M1

Historical M1 acceptance record. Current M2 execution/business migration is documented in [PROJECT_ASSISTANT_M2](PROJECT_ASSISTANT_M2.md); the original M1 no-upgrade/no-runner statements below describe that earlier round.

[简体中文](PROJECT_ASSISTANT_M1.zh-CN.md)

Implementation locally verified with provider substitutes; [ADR 0076](adr/0076-read-only-project-assistant.md). Source migration head is `20261031_0020`; the installed business database has not been upgraded.

Select a project in the Agent workspace, enter a goal and optionally choose up to 20 parsed document/code versions across source pages. No attachments means confirmed project knowledge only. Code uses exact selected local UUIDs, or an available saved commit containing every selected code version. Submit once and inspect saved scope, counters, tool events, typed report and exact references. Raw/code excerpts and confirmed evidence remain distinct. Referenced claims are not automatically semantically verified. Citations navigate to exact chunks where available, otherwise the exact source UUID. Clarification requires a new goal.

Tasks execute synchronously; history, polling, refresh and per-project session restoration are GET-only. Unknown submission outcomes require reading the saved UUID before explicitly resending it; replay never executes again. Expired execution is interrupted; new attempts require separately submitted UUIDs. Remote transport outcomes may be unknown even if the local task failed. M1 has no runner, cancel, continuation, note editor, imports or governed writes. No live model experiment is authorized; frozen data/ledgers and human coverage 0% are unchanged.

## Local verification (2026-10-31)

| Check | Observed result |
| --- | --- |
| Focused backend / migration / legacy progress | 61 passed; fresh `output/m1-focused-20261031-r2` |
| Full backend coverage | 1019 passed, 11 skipped; 95.44% against the unchanged 90% gate; `output/m1-full-20261031-r1` |
| PostgreSQL 17.10 / pgvector 0.8.7 | Isolated upgrade/downgrade/upgrade and 257 tests passed; disposable schema removed, business marker unchanged |
| Frontend coverage / type checks | 140 passed; lines75.30%, statements71%, branches63.89%, functions54.97%; existing gates passed |
| Final affected frontend / production build | 26 passed after the button-alignment adjustment; build passed |
| Delivery review | Working/staged `git diff --check` and changed Markdown local links passed; staged files exclude evaluation, generated output, dependencies, environment files and credential-pattern matches |
| Desktop system Chrome, 1440x1000 | Source pagination/selection, fixed commit, typed report, exact chunk navigation/focus, clarification, failure, empty state, refresh/reload and unknown-response GET recovery passed; no page errors or horizontal overflow |

The browser report combined two selected versions with confirmed knowledge: four references across source/code/knowledge, selected synthetic commit retained, 2 model / 3 tool / 0 embedding attempts. Refresh/reload held the substitute counter at2; clarification/failure added one each. A deliberately dropped successful response brought the counter to6; GET recovery cleared pending state without increasing it. Empty-project submission remained at6. All six were local function substitutes; external HTTP transports were blocked. A 780px output panel scrolled through1448px of expanded report/events with visible keyboard focus. The final refresh button height is36px. The isolated API's database/schema readiness returned up; the business schema was not upgraded.

Windows sandbox runs initially could not execute TestClient / Vite temporary renames; the authorized checks were rerun outside the sandbox using existing environments. A temporary QA setup needed Alembic URL escaping; its failed setup cleaned its owned schema before retry. Browser/API/Vite sessions are cleaned after acceptance; local ignored artifacts are under `output/m1-browser-20261031/` and coverage XML under `output/m1-backend-coverage.xml`. These results do not establish real model task quality, human grading or hosted Linux/container CI. M2–M5 remain planned.

The user selected Agent execution. Recorded results were actually executed using local provider substitutes. Prerequisites: existing `.venv` / `node_modules`, native PostgreSQL with pgvector in public and permission to create a disposable isolated schema. Model providers use local substitutes; no new dependencies or live calls are needed. Use fresh ignored output directories for each round.

```powershell
# backend
.\.venv\Scripts\python.exe -m pytest tests/test_project_assistant.py tests/test_migrations.py tests/test_multi_agent.py tests/test_agent_progress.py --basetemp ../output/m1-focused-temp
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-fail-under=90 --cov-report=term-missing --basetemp ../output/m1-full-temp
.\.venv\Scripts\python.exe -m scripts.verify_native
# frontend
npm run test:coverage
npm run build
# repository root
git diff --check
```

Expected: focused/full regressions pass, coverage >=90%, frontend checks/build pass; native isolated upgrade/downgrade/upgrade and scope/lease tests pass without changing the business migration marker. Inspect staged files for generated artifacts, dependencies and secrets. Desktop browser acceptance covers source pagination/selection, fixed snapshots, empty/missing/clarification/failure states, exact citations, unknown-submit recovery, refresh without POST, project fencing, keyboard focus, long text and panel scrolling, using local model substitutes. These checks do not measure live quality. Business database upgrades follow the separate backup/recovery workflow.
