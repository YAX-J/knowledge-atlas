---
name: ka-verify
description: Knowledge Atlas 的快速可靠验证、执行方确认与“完成”判定。修改后端、前端或文档后，用最小充分检查避开本机 Python、Windows 沙箱、浏览器安装、端口与 CORS 等已知耗时陷阱；可见界面只验收桌面端。
---

M3/M4 existing Agent executor selection persists. Run notes/assistant_workspace/workspace_migration with v1/v2 regression, full backend90% coverage, frontend coverage/build, native isolated migration+296 regressions and independent cancellation fencing, desktop Chrome notes/autosave/history/approval/reload/focus/scroll. All provider calls are substitutes. Business0021→0023 requires verified backup/schema restore and30 old business-table fingerprints. Review staged exclusions, paired links, git diff --check, then local commit; M5/live calls remain outside scope.



M2 user-selected Agent verification: focused87/1 skipped; full1036/12 skipped,95.42%; native274 including race and migration; frontend143/coverage/build, final backend16/1 skipped and frontend29/build; desktop queued-zero-call/reload, unknown ack, explicit continuation/tool reuse/free receipt replay, in-flight cancel, keyboard Space/Tab/Enter, empty/scope/scroll passed. Browser used a separate runner thread/session and blocked transports; actual CLI passed on empty business queue. Real readiness200 and backup/restore/fingerprints passed for0020 then0021. Keep real quality/hosted Docker CI separate and frozen ledgers/human0 unchanged.
# 验证方案与执行方确认

M5 offline preparation uses `python -m scripts.project_agent_m5 acceptance --full --native --frontend --output ../output/<fresh-name>` after the existing Agent executor choice. Pin the independent20-task packet,18 real test selectors and rubric via trusted SHA. `scripts.m5_offline` blocks real sync/async HTTP and propagates to native child pytest; preserve90%/frontend gates and physically owned schema cleanup. Engineering output saves command/exit/log hash/JUnit and stops on failure. Preflight reserves0 and is never a grant/live executor. Report external task/grade hashes, all attempted/graded/unattempted denominators, null ungraded metrics and separate human/model uncertainty. Hosted CI, real quality, final fresh tasks, demo and publication remain separate gates. No UI change needs a new browser round; label M34 evidence inherited. Preserve all preexisting evaluation/ledger/grant files; only the new versioned development packet is added.

## Project assistant M1 acceptance (ADR0076)

The user explicitly selected Agent execution. Focused61 and full1019/11 skipped passed, backend coverage95.44% with the existing90% gate. Native PostgreSQL17.10/pgvector0.8.7 isolated upgrade/downgrade/upgrade plus257 regressions passed without changing the business marker. Frontend140/coverage/build and final affected26 passed. System Chrome1440x1000 used a disposable native API with all provider transports blocked: typed source/code/knowledge references, exact chunk focus, cross-page selection/fixed commit, missing/ask/failure/empty states, unknown-response GET recovery, refresh/reload zero new calls, keyboard focus, wrapping and panel scroll passed. Preserve these as substitute engineering results, not live quality or hosted CI.

On this host, TestClient may hang silently and Vite can fail every suite before collection with temporary rename EPERM. Rerun authorized commands outside the sandbox, do not alter production semantics or reinstall dependencies. ListSources returns SourceListItem without content_sha256; scope selectors use exact source UUIDs and the backend binds hashes. Temporary Alembic URLs must escape percent signs only for Config interpolation; never log connection strings. Keep business schema upgrades separate from disposable acceptance and clean only owned browser sessions/ports/schemas. Final diff/staging checks and local commit follow acceptance; see paired PROJECT_ASSISTANT_M1 guides.

本技能只做一件事：在说“实现完成”之前，按改动范围准备足够、可复现且不过度的验证步骤，由用户选择执行方，并如实报告结果。仓库现有 CI 定义与组件/API 测试，仍不能省略本地与真实服务验证。

仓库级规则：执行验证前先提供步骤、命令、前置条件和预期结果，再询问由用户还是 Agent 执行。用户选择 Agent 前不得自行运行；当前请求已经明确选择时无需再次询问。Agent 实际执行通过或用户反馈通过后，才可将对应项目标为已验证。

浏览器验收只做桌面端，不设置手机视口、不截取手机截图，也不把手机端走查列入测试计划。响应式样式仍可在实现时维护，但不属于默认验收范围。

## 何时使用

- 任何代码、迁移、文档改动之后，用于生成测试步骤并确认执行方。
- 准备提交或回复“实现完成、待验证”之前。
- 排查“本地能过、真实服务不过”的差异。

## 黄金规则

- 运行前提供命令、前置条件和预期结果，并记录用户选择的执行方。
- 只有 Agent 在用户选择后实际执行，或用户提供了结果时，才报告命令结果。
- SQLite 测试通过 ≠ PostgreSQL 验收通过。
- `npm run build` 通过 ≠ 浏览器交互正确。
- 不把 Mock 响应说成真实模型质量。
- 不把“文档已写”说成“功能已实现”。
- 先跑与改动直接相关的聚焦测试，再跑一次完整后端测试；代码未变化时不重复跑同一套完整测试。
- 只有可见 UI 发生变化时才启动真实浏览器；纯后端、测试或文档改动不启动前端服务。

## 省时执行顺序

1. 根据改动列出聚焦测试、完整测试、构建和桌面浏览器步骤，先让用户选择执行方。
2. 后端先跑相关测试文件，快速暴露局部错误；通过后只跑一次完整 `pytest`。
3. 前端只跑一次 `npm run build`。仅当可见 UI 改动时，再启动真实 API/前端做桌面浏览器走查。
4. 浏览器只覆盖本轮变更路径及直接相邻状态，不为未改动页面重复做全站回归。
5. 最后运行 `git diff --check`、检查跟踪文件和暂存补丁；代码在这些步骤之间未变化时不重跑前面的测试。

## 已知耗时与易错点

- **错误的 Python**：不要先尝试 PATH 中的 `python`。进入 `backend/` 后直接使用 `.\.venv\Scripts\python.exe -m pytest`，避免因全局环境缺少 FastAPI 等依赖而产生无效失败。
- **Windows 沙箱内 TestClient 卡住**：若测试长时间无输出，堆栈停在 Starlette/httpx `TestClient`、`asyncio` socket pair 一带，这是已知运行环境限制。停止该进程，说明原因，并在取得所需执行权限后用同一个项目虚拟环境命令重跑；不要因此修改业务代码或重装依赖。
- **重复下载浏览器**：桌面浏览器优先使用已安装的系统 Chrome，并给自动化工具传入其可执行路径。系统 Chrome 可用时，不下载 Playwright/agent-browser 自带 Chromium。
- **端口误伤**：先查看既有服务。不要停止用户已运行的 `8000`/`5173` 服务；确需隔离时使用专用端口（例如 API `8001`、Vite `5174`）和有名称的会话，结束后只清理自己启动的进程。
- **CORS 配置不一致**：隔离启动前就把后端允许源设为实际 Vite origin，并把前端 API 地址指向对应 API 端口；不要启动后再靠反复重启猜配置。
- **浏览器请求拦截不稳定**：不要为了补一个页面状态反复搭建缺少 CORS 头的 route mock。优先使用现有测试数据；没有安全前置条件时，以聚焦 API 测试和生产构建覆盖，并把未做的真实交互明确列为限制。
- **昂贵或有副作用的外部调用**：除非本轮明确要求真实验收，否则不调用 DeepSeek、不重新同步 GitHub、不点击会改变外部状态的控件。Mock、模拟响应和真实服务结果必须分开报告。
- **服务清理**：记录自己启动的会话与端口。浏览器完成后关闭命名会话和专用服务，再确认端口已释放；不得按进程名批量结束用户进程。

## 建议的快速命令

```powershell
# 仓库根目录
git diff --check
git status --short

# 后端
Set-Location backend
.\.venv\Scripts\python.exe -m pytest

# 前端
Set-Location ..\frontend
npm run build
```

按改动追加：

| 改动 | 追加检查 |
| --- | --- |
| 抽取/审核/图谱 | `.\.venv\Scripts\python.exe -m pytest tests/test_knowledge.py tests/test_graph.py` |
| 关键词检索 | `.\.venv\Scripts\python.exe -m pytest tests/test_search.py`；原生 PostgreSQL 验证排序、证据、多词、通配符；浏览器检查清空、重试、类型、详情和迟到响应 |
| 语义检索 | `.\.venv\Scripts\python.exe -m pytest tests/test_search.py tests/test_migrations.py`；原生 PostgreSQL 验证 1024 维写入和余弦排序；真实嵌入服务验收必须单独注明 |
| 混合检索 | `.\.venv\Scripts\python.exe -m pytest tests/test_search.py tests/test_graph.py`；验证归一化组成得分、关系归档/时间过滤、稳定排序；真实 PostgreSQL 与嵌入服务验收单独注明 |
| 证据问答 | `.\.venv\Scripts\python.exe -m pytest tests/test_questions.py tests/test_search.py`；验证无证据不调用模型、严格引用归属、错误映射、切换项目迟到响应；真实 DeepSeek 质量单独注明 |
| 导入/解析/Worker | `.\.venv\Scripts\python.exe -m pytest tests/test_sources.py tests/test_parsing.py tests/test_worker.py` |
| 迁移/模型 | `.\.venv\Scripts\python.exe -m pytest tests/test_migrations.py` + `.\.venv\Scripts\alembic.exe upgrade head` |
| 前端可见界面 | 只做真实浏览器桌面端走查；不做手机端测试 |
| 文档 | 双语链接、命令、状态标注 |

## 后端清单

- [ ] `python -m pytest` 全绿，或明确列出失败用例与原因。
- [ ] 新行为有聚焦测试，不只靠手工验证。
- [ ] 迁移可升降级，离线 SQL 可编译。
- [ ] 真实 PostgreSQL：`alembic upgrade head` 成功，`GET /api/v1/health/ready` 返回 `up`。
- [ ] Worker 改动：`python -m app.worker --once` 冒烟，退出码符合预期。
- [ ] 没有把密钥、完整原文、模型响应写进日志或测试。
- [ ] 错误仍走统一 `error` 结构，未新增未处理的 500。

## 前端清单

- [ ] `npm run build` 通过（含 `vue-tsc`）。
- [ ] 桌面宽度下：无横向溢出、面板可滚动、长文件名/长知识名不撑破布局。
- [ ] 加载、空数据、错误、重试四种状态都能到达且有反馈。
- [ ] 键盘可完成主要操作，焦点可见；`prefers-reduced-motion` 下动效收敛。
- [ ] 原文只做文本插值，没有 `v-html`。
- [ ] 真实接口失败时展示错误，不回退成假数据。
- [ ] 图谱页：节点/关系可选，详情证据可读，筛选/深度/返回总览可用。
- [ ] 问答页：支持/不足/错误状态可达，引用可跳实体，切换项目不保留旧回答。

## 真实服务验收（涉及导入/抽取/图谱时）

1. 启动本机 PostgreSQL（含 pgvector），确认 `backend/.env` 的 `DATABASE_URL`。
2. 在 `backend/` 运行 `.\.venv\Scripts\alembic.exe upgrade head`，再用 `.\.venv\Scripts\uvicorn.exe app.main:app --reload` 启动 API。
3. 另开终端运行 `.\.venv\Scripts\python.exe -m app.worker`（或按需 `--once`）。
4. 创建项目 → 上传 Markdown → 解析 → 查看分块行号。
5. 重复上传相同字节，确认复用来源/任务。
6. 抽取候选（真实 key 或模拟响应，注明是哪种）→ 确认实体 → 确认关系 → 查看项目图谱与证据。
7. 重启 API，确认数据仍在。
8. 记录哪些步骤通过、哪些仍是已知限制。

## 文档清单

- [ ] 改 API 形状 → `docs/API_CONTRACT.md`。
- [ ] 改知识模型 → `docs/KNOWLEDGE_MODEL.md`。
- [ ] 改架构决策 → 新 ADR。
- [ ] 改能力/安装/结构 → `README.md`。
- [ ] 变更记录进 `CHANGELOG.md` 的 `Unreleased`。
- [ ] 有 `.zh-CN.md` 的文档成对更新，语言链接有效。
- [ ] 计划中的能力仍明确标注“规划中”。

## 提交前

- [ ] 只暂存本轮相关文件，保留无关的用户改动。
- [ ] `git diff --cached` 逐块看过，没有调试代码、生成物、`.env`。
- [ ] 提交信息描述最终行为，而不是“update files”。
- [ ] 提交后报告哈希与仍未提交的改动。
- [ ] 无法提交时保留工作并说明原因，不谎报成功。

## 报告模板

```text
验证计划：
- cd backend; .\.venv\Scripts\python.exe -m pytest
  预期：全部用例通过。
- cd ../frontend && npm run build
  预期：类型检查与生产构建成功。
- cd .. && git diff --check
  预期：无输出。

执行方：
- 用户选择 Agent 执行。

实际结果：
- 逐项填写实际命令、通过/失败和必要输出摘要。

结论：
- 仅在上述检查实际通过后写“已验证”；真实服务与模型质量仍需按前提分别验收。
```

## 环境说明

- BM25/空索引优化：聚焦 `tests/test_lexical_search.py tests/test_search.py tests/test_run_evaluation.py tests/test_questions.py`，前端 `npm run test:coverage` 与 build；原生临时 schema 现包含词法/截断/空索引零调用。`scripts.run_evaluation --modes keyword bm25` 对准备项目只读执行，不加供应商标志，不跑回答；新结果必须单独保存，不能覆盖旧三组基线或把开发集成绩当盲测。

- 阶段六初始化/基线：先运行 `python -m scripts.prepare_evaluation --dataset ../evaluation --validate-only`；聚焦 `tests/test_prepare_evaluation.py tests/test_run_baselines.py tests/test_run_evaluation.py tests/test_evaluation_dataset.py`。正常单测模拟供应商；真实 `scripts.run_baselines --allow-embedding-calls` 需沿用用户明确的本轮授权。默认每批10条，44实体首次索引5请求，40题向量/混合80请求，回答为零。失败报告不覆盖，账单未知保持 null。`scripts.verify_native` 现包含新项目初始化验收并清理临时 schema。

- `python -m scripts.verify_native` 在随机 schema 做原生迁移、时序/仓库集成、独立会话竞争与 Worker fencing；显式指定 Alembic 版本表 schema 并检查全部本地表，不能只设 search_path。`--github` 仅在用户明确允许公开 GitHub 只读验收时运行，不用令牌/模型，普通 pytest 跳过原生/外网用例。

- 默认验收路径是用户本机原生 PostgreSQL 17 + pgvector；Docker Compose 可选，不是前提。
- 后端测试用内存 SQLite，不验证行锁、组合外键强制、扩展和并发。
- 若 shell / 构建环境不可用（例如沙箱文件权限问题），直接说明“无法运行”，不要用静态阅读冒充验证结果。

## 2026-10-25 optimization checks

For optional RRF, source review totals and summary-group governance, include `tests/test_retrieval_optimization.py` and `tests/test_maintenance_optimization.py`; native acceptance now runs both. Browser checks cover question retrieval selection/stop-wait, whole-source progress and governance entity navigation. Existing no-paid-provider and executor-selection rules still apply.

## Native QA isolation and batch/index checks

Add `tests/test_batch_reviews.py` and `tests/test_embedding_status.py` for ADR 0046; verify_native includes both. Before writing ANY temporary PostgreSQL fixture, assert that the temporary schema physically owns every required business table. `current_schema()` alone is insufficient: SQLAlchemy create_all existence checks may see public tables via search_path and skip private creation. Use explicit-schema migrations or forced creation with ownership assertions, then assert fixture UUIDs are absent from public. Always clean only recorded, validated temporary schema/fixture identifiers.

## Discovery checks (ADR 0047)

Include tests/test_knowledge_discovery.py in focused and native acceptance. Desktop checks cover combined review filters/empty results with unchanged source totals, governance filtering before limits, separate comparison quotes with focus/error/retry, and one question passage with related entity navigation. App regressions must reject stale filter responses and wrong-project/closed comparison results. Continue enforcing temporary-table ownership before fixture writes and recorded-schema-only cleanup; model/embedding stubs do not establish provider quality.

## Search lifecycle verification

For search/index composable changes, focus frontend/tests/knowledgeSearchState.test.ts and frontend/tests/appRequests.test.ts, then run full frontend coverage and build. Coverage now includes useKnowledgeSearch.ts; report its scoped denominator accurately. Browser response-delay checks may hold a local rebuild response: clearing must keep the rebuild control disabled until settlement, suppress old notices and avoid another request. Normal rebuild must retain BM25 results without another lexical request. Provider stubs and native fixture persistence are separate from full native migration/contention acceptance.

## Relation dependency acceptance (ADR 0048)

Focus tests/test_knowledge_discovery.py tests/test_batch_reviews.py tests/test_knowledge.py and frontend/tests/review.test.ts tests/appRequests.test.ts. Native includes the discovery file. Desktop acceptance: filter to relations while endpoints are pending, verify disabled confirmation and named batch warnings, navigate to entities with cleared selection/preview and heading focus, explicitly confirm entities then the relation. Keep no-real-provider and temporary-schema ownership/cleanup rules.

## Source discovery acceptance (ADR 0049)

Focus tests/test_source_filters.py tests/test_sources.py plus frontend workspace/App/client regressions. Native acceptance includes the source filter suite. Desktop: combine literal path punctuation/language/source status, verify zero-match guidance with original preserved, reset, and simulate one second-page read failure to confirm retry reaches page two. Confirm list heading focus and no horizontal clipping. Continue physical private-table ownership checks before fixture writes and recorded-schema cleanup; providers remain stubbed.

## Optimization items 1–3 verification

Focus tests/test_embedding_jobs.py tests/test_source_retrieval.py tests/test_database_backup.py tests/test_migrations.py tests/test_run_evaluation.py. Native includes job concurrency/fencing, migration 0016 and source cases; verify every metadata table physically belongs to its disposable schema. Frontend covers recovered busy state, explicit interrupted retry, uncertain-result inspection and model budgets. Desktop reload during a blocked local stub, release it, inspect completion, then simulate lost success response with exactly one POST. Backup rehearsal must compare complete data/type/constraint/index/extension fingerprints, verify no foreign keys to public, and clean only owned targets. Record CREATE DATABASE permission failures separately from successful schema rehearsal; never grant privileges or report full DB restore without acceptance.

## Optimization 4–6 acceptance

Focus tests/test_read_performance.py tests/test_retirement.py plus migration/graph/search; verify_native includes both and an independent-session retirement race. Count SELECT reads separately from transaction/savepoint statements and scope fixture queries to their own project even when other native tests commit fixtures. benchmark_reads runs a random physically-owned native schema with no providers, records three fresh-session query/time/tracemalloc samples and cleans only itself; retain versioned before/after JSON and normalized-output hashes, never infer HTTP/RSS/capacity or answer quality. Frontend focus orchestration.test.ts retirement.test.ts appRequests.test.ts, full scoped coverage/build, then real desktop upload/parse/stub extraction/review/entity+relationship retirement/audit/history checks. Check browser focus/overflow/errors and clean only recorded processes/schema. Clean QA before final public-only backup/schema recovery.

## 2026-10-26 功能补全更新

功能补全检查包含 workspace/conversations/GitHub continuation、KA_NATIVE_COMPILERS=1 的 Java/TS/Go 实机测试，以及独立 schema 的 verify_native。付费公开实验累计账本有 120/160 上限，失败/未知也计入，不得重置；离线盲评空白不能冒充真实人工评分。

## 2026-10-29 当前优化边界

Final scope now includes criticalFlows, workspaceRoute, projectGraphFlow and orchestration frontend regressions; snapshot/identity/embedding-plan/holdout backend regressions; native verify includes code contexts. Prefer native schema testing to catch PostgreSQL JSON DISTINCT differences. benchmark_scale creates/removes its own schema for1k/10k normal-reviewed synthetic fixtures,20 warm samples, no providers; record p95/SQL/Python allocations, not RSS or production SLA. Cold embedding batch counts are estimates, not calls/authorization. Human blind grading remains explicitly deferred.

## Single-project multi-agent extension (ADR0064–0065)

Multi-agent checks: tests/test_multi_agent.py and test_agent_tools.py; full backend KA_NATIVE_COMPILERS=1 coverage>=90%, scripts.verify_native owned-schema migration roundtrip and scoped workflows; frontend agentRuns/workspaceRoute plus coverage/build. Native tests share committed fixture schema: assertions must filter their own project/source. Browser qa_workspace supplies local tool-call protocol stubs and requires zero real provider calls; start/list/read, reload, review/resume, QA/evidence links, focus/empty/scroll/overflow. Stop only recorded owned processes, clean only recorded schema before public-only backup. Keep frozen evaluation files and84/61 cumulative ledger unchanged.

## Batched lexical v2 (ADR 0066)

Include tests/test_batched_lexical.py with lexical/source/retrieval/read-performance/question/evaluation regressions; verify_native includes the new file. Check the unique match beyond 1000, global statistics including unmatched/empty documents, batch-independent scores, duplicate-name cursors, per-canonical-entity evidence limits and independent Top K/scan/text truncation. Scope/history checks must also cross batch boundaries. Frontend types accept v1/v2 metadata; no browser is required when visible UI is unchanged. Preserve frozen evaluation assets and use v2 identifiers only in new runs; do not attribute historical v1 metrics to v2. Windows sandbox TestClient can stall after pure-service cases; stop that owned process and rerun the same venv command outside the sandbox after execution permission is available.

## Durable agent progress (ADR 0067)

Focus test_agent_progress.py, test_multi_agent.py, test_agent_tools.py, test_knowledge.py, test_questions.py and test_conversations.py. Native verify includes an independent-connection observer of a blocked provider: the reservation must already be committed, replay must not issue another call, and stale ownership must block further attempts. Cover pending-write refusal, sanitized storage failure, partial-result retention and crash readback. Checkpoint label changes require frontend coverage/build and a named desktop Chrome walkthrough; use qa_workspace local substitutes/owned schema, then close only recorded services and verify cleanup. Existing executor choice persists for a continuing authorized optimization task.

## Explicit workflow scope (ADR 0068)

Focus frontend agentScope/agentRuns/workspaceRoute/client and backend test_agent_scope/test_multi_agent/test_code_context/test_agent_progress, then relevant full/native checks. verify_native includes test_agent_scope. Cover source/project round trips, metadata failures blocking paid submission, fixed/local exclusion, history/current-code exclusion, aware UTC conversion and allowlisted saved scope reads. Browser fixtures may add normal synthetic local versions and synthetic snapshot manifests only inside a schema whose every business table is verified physically owned; label them synthetic and never count them as GitHub/provider-quality acceptance. Close named browser/recorded services and confirm ports/schema cleanup; frozen evaluation and paid ledger stay unchanged.


## Claim-level QA acceptance (ADR 0069)

Include test_answer_claims/test_questions/test_conversations/test_multi_agent/test_run_evaluation/test_model_acceptance plus frontend answerClaims/discovery/agentRuns/agentScope. Native verify includes test_answer_claims. Cover per-claim missing/forged/foreign IDs, partial support, stable union order and budget, strict provider/tool parsing without flat fallback or automatic retry, and old persisted read/same-UUID replay. Run full backend coverage with KA_NATIVE_COMPILERS=1, owned-schema native checks, frontend coverage/build, then desktop exact chunk navigation, no-evidence refusal, persisted reload, legacy notice, focus and scrolling using local substitutes only. Clean named browser, recorded servers and physically-owned schema. Never equate structural checks or stubs with semantic correctness or human grades. Existing Agent executor choice persists for continued optimization.


## Batched workflow list checks

For workflow read optimizations, include tests/test_agent_list_performance.py, test_multi_agent.py, test_agent_scope.py, test_agent_progress.py and test_read_performance.py. Native verify includes the list suite. Instrument SELECTs separately from transaction statements and compare full output with the legacy detail-per-row path: candidate pages of1/10/50 should use4 reads instead of6/33/153; empty/candidate-free pages use3. Cover exact candidate-ID subsets, overlapping extraction reuse, duplicate/missing IDs, source/task/user/project boundaries, tied pagination, stale ORM refresh and lease edges with a fixed clock. Candidate count projections must not load payload/name/summary. Reads never call providers or write expiry status. No browser/frontend build is needed for backend-only changes with the existing response shape. Report SQL counts as such, without inferred HTTP speedup, atomic snapshot or production capacity. Existing Agent executor authorization persists.


## Ordered read optimizations and Jev-only checks (ADR0070–0071)

Include test_symbol_cache, test_agent_summary, test_jev_evaluation with code_search/multilanguage/java and legacy agent suites; verify_native includes the new files. Assert immutable IDs, parser-budget/version misses, accounted LRU bounds, flags and scope/readiness before cache. Summary SQL/JSON must exclude result/events/request/usage, keep3 SELECTs and preserve default full responses. Jev unit/local preflight never contacts a provider, keeps human0 and model grades0 in dry mode; failures reserve once without retry. Native benchmarks use owned schemas and new versioned outputs, never touch frozen prior results. Cache timings exclude DB/HTTP; tracemalloc is not RSS,3 samples do not establish p95/SLA. The user explicitly selects no live Jev calls this turn. Full backend/native/frontend checks and desktop form/detail/focus/scroll plus diff/link/staged review complete this slice.


## Cloudflare offline judge checks (ADR0072)

Include tests/test_cloudflare_evaluation.py and test_jev_evaluation.py with evaluation regressions, then one complete backend coverage run. MockTransport covers native envelopes, decision labels/probabilities, chat JSON Schema and absent confidence, configuration, 401/429/redirect/timeout/size/usage errors, no retries/fallback, reservations before HTTP, missing auth/caps, order/low-confidence uncertainty and CLI authorization. Run provider-free CLI preflights for CF decision, CF chat and explicit Jev in new ignored outputs; no real calls. This backend/config-only change needs no browser or frontend rebuild. Inspect paired guides, local ignored .env fields, diff/staging and frozen-artifact exclusions. Existing Agent executor choice persists.


## OpenRouter judge checks (ADR0073)

Focus test_openrouter_evaluation with CF/Jev/run/model-acceptance suites, then one full backend coverage run. HTTP substitutes cover the fixed Decisions endpoint, explicit version/snapshot matching, drift stop, exact choices/probabilities/usage/cost, HTTP/JSON/size/timeout errors, proxy-aware construction, no fallback/retry, anonymous reference separation, disk reservation, CLI provider/cap/auth boundaries and preserved partial outcomes. CLI preflight for OpenRouter, direct Jev and native Clef must reserve/complete0 and use fresh ignored outputs; no live account/model/billing calls. No front/UI/SQL changes, so no browser/build/native DB rerun. Keep .env ignored and review bilingual links/staging. Existing Agent executor selection persists.

## Current online evaluation checks (2026-10-31)

Include tests/test_evaluation_diagnostics.py with run_evaluation, answer_claims, jev_evaluation and cloudflare_evaluation, then one full backend run. The new suite exercises complete96-answer SQLite/local-provider exports, per-case historical time, exact claim/input-pool attribution, frozen-score projections, before-call reservations, failure/no-retry and budget/approved-plan rejection before services. These substitute results are engineering checks, never holdout quality scores. CLI diagnostics/preflight must be provider-free, preserve historical inputs/ledgers and use fresh output directories. On this Windows host use an explicit fresh --basetemp under output; outside-sandbox TestClient may be required. Review bilingual experiment/diagnostic reports, input hashes, exact frozen-file exclusions and staged diff. No UI/schema change requires a frontend build/browser or native DB rerun. User selected Agent-run offline verification for this ordered task; live provider authorization remains separate.

## Live round verification and partial failure (2026-10-31)

Focused evaluation_diagnostics/public_protocol checks cover scoped-grant mismatch/exhaustion/counter integrity/locks/unique output, historical ledger preservation and both complete/fail-stop local substitutes. Grant changes passed33 focused and941 full/11 skipped; final sanitized-error metadata passed34 focused. Native live preparation and independent cleanup checks succeeded, but model request5 failed; never describe unit/native success as completed model quality. Archive original partial/run/grant/preflight/cleanup records, preserve raw schema_removed=false and document the independent cleanup proof. Record the base64-encoded patch in executed-code.json against the starting commit when observability changes occur after the live attempt. Verify exact partial citation lines, artifact hashes, unchanged historical ledger/frozen inputs, paired docs and staged exclusions. Do not retry providers merely to verify a failure.

## Repaired offline execution verification: ADR0074

Focused evaluation_diagnostics/answer_claims/public_protocol/jev_evaluation/cloudflare_evaluation passed129; one full backend run passed951/11 skipped. Test all-invalid local-substitute completion with no fabricated answers, default/transport fail-stop, exact diagnostic reuse/mismatch refusal before providers, scope/model/protocol changes, and explicit hashed judge exclusions/default rejection. Verify live v4 records cover96 cases,91 valid/5 null failures with human0, diagnostic1+main95/73 within96/73, exact quoted passages, sealed prior ledgers and owned-schema cleanup. Compare reused passage sequences/UUID mappings and preserve original latency/provenance. Renderer output must label retrieval/output coverage, never unmeasured semantic accuracy. Judge preflight457 reserves/completes0; preserve packet/exclusion hashes. Execution protocol was revised after observed failure and one answer reused: disclose both. Do not use holdout to tune prompts/ranking/thresholds or automatically invoke judges.

## Offline judge-summary verification (2026-10-31)

tests/test_judge_summary.py with Jev/Cloudflare suites passed76; one full backend run passed960/11 skipped. Cover all-case versus graded denominators, invalid outputs remaining null, low-confidence/order support, source immutability, packet/config/exclusion/mapping/answer tampering, duplicate jobs, output overwrite and explicit partial summaries without invented grades. Live457/457 completion is separate from test success. Verify new source run against authorization packet/config hashes, all historical ledger/input SHA-256 values, source QA fields remaining human-null, archive byte preservation, exact uncertainty lists/183 units and zero summary provider calls. Charts must label model judgments, not human accuracy. Paper/demo Markdown is a draft; examples are selected illustrations, temporary DB remains cleaned, no live demo calls. Preserve source run2 results; new judging belongs in a separate result directory with byte-preserving Git attributes.

## Server-derived answer support checks (ADR0075)

The existing Agent executor selection persists for ordered steps1–2. Run test_claim_support_v3, answer_claims, questions, conversations, multi_agent, run_evaluation and evaluation_diagnostics with a fresh output --basetemp, then the full backend suite. Focus passed118; full passed994/11 skipped. Verify HTTP substitutes for single_step/tools: all-supported/mixed/all-insufficient/shared citations, no model aggregate Schema field, redundant aggregates rejected once without retry, invalid/missing/foreign citations, budgets, old flat/v2 reads and same-UUID replay, new v3 exports and v2 reuse refusal. New development fixture must be independent of frozen data/judgments. Frontend answerClaims passed5 (both protocol versions), npm run build passed; types/tests only, no visible UI/browser/native DB check needed. No real providers or v3 quality estimate. Check bilingual links, frozen tracked evaluation artifacts, git diff --check and staged exclusions. Preserve historical failures and all ledgers/grants; never relabel v2 outputs as v3.

## GitHub CI portability failures (2026-10-31)

When Windows tests pass but a fresh Python-only Linux job fails, compare settings and dependency preconditions before changing production errors or installing unrelated SDKs. Mocked compiler process-failure tests must create a temporary backend/frontend dependency layout and substitute the process; assert one attempted invocation. Independently test missing TypeScript package rejection before process start. API tests using extraction's configured fixture must also inject settings into question routes; local .env credentials must not conceal missing test configuration. Verify provider stub counts for irrelevant retrieved evidence and zero calls on empty retrieval. Preserve production validators, existing skip gates and the 90% CI coverage threshold.

For Actions PostgreSQL services keep --health-cmd "pg_isready -U knowledge_atlas -d knowledge_atlas" double-quoted. Shell single quotes in service options can leave -U exposed as a Docker flag before any checkout/test runs. Check YAML and process argument grouping, then distinguish these checks from Docker startup/native database acceptance. If Docker is absent locally, report it and leave hosted postgres validation pending a new-commit workflow run. Never claim a local Windows test pass is a green Linux/container workflow, rerun an old commit expecting new code, or push/publish/move baseline tags without explicit authorization.

Focus test_semantic_analysis/test_source_retrieval/test_questions, then run the CI backend command with --cov=app --cov-fail-under=90 --cov-report=term-missing --cov-report=xml:../output/backend-coverage-ci-portability.xml and a fresh --basetemp. Run both prepare_evaluation and evaluate_calls --validate-only steps. Review bilingual setup/changelog, frozen evaluation exclusions and git diff --check. No frontend/browser, production-schema migration or live providers are needed for these fixture/YAML changes. The user's existing Agent executor selection persists.

Observed local Windows/Python3.13 results: focused27 passed/3 skipped; full995 passed/11 skipped, coverage95.45% with the unchanged90% gate. Both validate-only commands and YAML/process argument checks passed. Docker is not installed on this host; hosted Linux/container startup remains pending a new-commit workflow run. No real provider calls or frozen evaluation changes.
