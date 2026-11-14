# Knowledge Atlas

M5 离线准备（2026-10-31）：已实现冻结的独立20项开发任务、18项验收矩阵、零调用预演、任务/评分导入及统一工程验收命令。M5 整体仍待授权后的真实执行器/夹具重放、真实质量、托管 CI、演示和发布。真实调用为零，无业务迁移，库版本保持0023；历史评估/授权/账本不变。见 [M5 状态与操作说明](docs/PROJECT_ASSISTANT_M5.zh-CN.md)。

Current 2026-10-31: M3–M4 implement immutable editable notes and capability-scoped project actions with exact human approval (ADR0078–0079). Source/business head is `20261031_0023`, upgraded after a 31-table backup/verified isolated restore; all 30 old business-table content fingerprints were preserved. See [M3/M4 implementation and validation](docs/PROJECT_ASSISTANT_M34.md). M5 remains deferred; this work uses local substitutes with zero live providers and preserves frozen evaluations/ledgers and human0%.

此前 M2 验收：异步排队、独立 runner、逐步检查点/尝试回执、取消和显式继续。M2 当时业务库与源码 head 为 `20261031_0021`，迁移前备份/隔离恢复及旧表指纹核验通过。见[使用与验收](docs/PROJECT_ASSISTANT_M2.zh-CN.md)及 [ADR0077](docs/adr/0077-durable-assistant-execution.zh-CN.md)。M3/M4 后续实现见上方当前说明，零真实模型调用。

2026-10-31：已完成回答格式与独立开发验证两项：新 `evidence-claims-v3` 由后端计算总体 supported，模型只给逐条结论、置信度和缺失信息；严格引用和旧记录读取保持。见 [ADR0075](docs/adr/0075-server-derived-answer-support.zh-CN.md) 与[合成开发检查](evaluation/development/claim-support-v3/README.zh-CN.md)。本轮零真实调用，v3 真实质量未测量；[既有457次裁判结果](evaluation/results/2026-10-31-holdout-v3-clef-run1/REPORT.zh-CN.md)属于历史 v2，失败、分数、输入和账本保持，人工覆盖率0%。

当前离线评审支持 OpenRouter Jev、直连 TypeSafe Jev 和 CF 原生评审，人工评分覆盖率0%。本轮新增 OpenRouter Decisions API、版本/日期快照校验、代理支持及零调用预演；尚未运行真实 OpenRouter 评审。配置见 [OpenRouter](docs/OPENROUTER_EVALUATION.zh-CN.md)、[CF](docs/CLOUDFLARE_EVALUATION.zh-CN.md) 和 [ADR0073](docs/adr/0073-openrouter-jev-evaluation.zh-CN.md)。此前读取优化保留 ADR0071 记录。

回答现按结论逐条绑定引用，证据不足单独标明，并可直接跳原文；历史记录仍保留旧格式，不自动补推对应关系。引用归属校验不证明结论语义正确，评估现采用 OpenRouter Jev、直连 TypeSafe 或 CF 原生匿名评审，人工覆盖率0%。见 [ADR 0069](docs/adr/0069-answer-claim-evidence.zh-CN.md)。

Knowledge Atlas 是面向毕业设计的个人技术知识系统。默认流程从你写的技术笔记开始。打开「工作台 → 打开项目笔记」，保存 Markdown 后点击「分析笔记并提取知识」。Agent 从所选修订提取实体和关系，你可以核对原文后确认入图。之后可在时序图谱、检索和问答中回溯证据。前端使用 Vue 3，后端使用 FastAPI，业务数据保存在 PostgreSQL + pgvector。

项目关系图支持切换到 Neo4j、手动同步正式知识快照、查看一跳或两跳邻域及定位原文证据。见 [Neo4j 本机配置](docs/DEVELOPMENT_SETUP.zh-CN.md#可选的-neo4j-图谱快照)。

资料页支持按固定 GitHub 提交分批同步整个仓库，解析 Worker 自动消费导入的受支持文件。见 [GitHub 快照导入](docs/DEVELOPMENT_SETUP.zh-CN.md#github-快照导入)。

项目助手支持整仓后台任务，按固定提交分批导入和解析，再用选取的资料生成带原文引用的报告。见 [整仓助手任务](docs/PROJECT_ASSISTANT_M34.zh-CN.md#整仓助手任务)。

当前能力、验收边界和后续工作以本页、[当前计划](PLANS.zh-CN.md)、[路线图](docs/ROADMAP.md)及[多 Agent 改造](docs/MULTI_AGENT.zh-CN.md)及[此前优化验收](docs/OPTIMIZATION_20261029.zh-CN.md)为准。此前逐轮检查点已移入[历史文档](docs/archive/pre-optimization-20261029/README.md)，旧实验数字保持不变。

## 当前可用能力

| 环节 | 实现与使用边界 |
| --- | --- |
| 技术笔记与资料 | 可编辑的 Markdown 项目笔记、历史修订和一键分析。资料库支持 Markdown、多语言代码、文件夹、GitHub 固定提交及 Issue/PR/Review/thread 版本 |
| 抽取与审核 | 结构化候选与精确原文校验。可从笔记提出事实有效期，用户核对或修正后确认入图，系统保存审核记录 |
| 图谱与治理 | 真实节点/关系、证据定位、历史有效期、替代链和分组演化、别名、合并/解除、撤回/启用、冲突检查 |
| 检索与问答 | 关键词、BM25、来源位置 BM25、向量、混合与 RRF；严格引用、无证据拒答、持久化会话及有界多轮上下文 |
| 代码分析 | 语法结构、静态候选、单轮/只读工具 Agent；显式 Java/TypeScript/Go 编译器声明解析；可选固定提交/本地重复路径版本 |
| 工作台 | 真实业务为默认入口，独立 Mock 演示；URL 恢复项目/来源/知识/历史时间/会话；图谱按关系、检索、身份、演化、停用分区 |
| Agent 协作 | 三个专业角色、两条固定 LangGraph 流程及独立 M2 项目只读助手及异步 runner/取消/显式继续；显式选择检索方式、历史时间和代码版本，保存请求范围、调用计数及步骤结果；候选等待人工审核后显式恢复 |
| 验证工具 | 迁移、备份/隔离恢复、原生数据库流程验证、公开实验、盲评工具、千级/万级合成性能测量 |

代码分析始终只读，不运行用户代码、构建脚本或自动写入正式图谱。编译器结果是静态声明身份，不代表完整构建上下文或运行时派发。扫描预算和截断会明确显示。

BM25 与来源位置 BM25 使用 v2 分批协议：每批 200 个实体，在最多 50,000 个可见实体上统一统计和打分，每实体最多 32 条排序证据、4000 字符排序文本。返回匹配数和独立的结果截断标记；不再只检索前 1000 个实体。RRF 的词法路沿用该协议；关键词和固定混合模式不变。实现与验收边界见 [ADR 0066](docs/adr/0066-batched-global-lexical-retrieval.zh-CN.md)，既有实验数字仍代表旧协议。

## 本地启动

先安装 Python、Node.js、原生 PostgreSQL 及 pgvector，并按[环境配置](docs/DEVELOPMENT_SETUP.zh-CN.md)填写后端 `.env`。已有数据先按[备份恢复](docs/BACKUP_RESTORE.zh-CN.md)备份；业务库/源码迁移 head 为 `20261031_0023`（已验证备份/恢复后升级）。就绪检查会拒绝落后、未迁移或缺少关键表/列的数据库。

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,evaluation]"
cd ..\frontend
npm ci
cd ..
.\scripts\start-demo.ps1 -Seed
```

已有虚拟环境时跳过创建步骤。脚本说明、独立 API/Worker 命令及可选 Docker 方案见[演示指南](docs/DEMO.zh-CN.md)。启动和只读状态查询不产生模型费用；抽取、问答、Agent 和索引更新需要显式操作。

## 验收与限制

- 应用库已备份、验证隔离恢复并升级至 `0019`，新增 `agent_runs`；24 张既有业务表内容指纹保持一致。备份只保存在忽略的本地输出目录。
- 本轮使用原生临时 schema 和本地模型替身验证功能；不把替身当真实模型质量。付费公开实验累计账本仍为 84 次模型 /61 次嵌入，本轮没有新增调用。
- [holdout-v3](evaluation/holdout-v3/README.zh-CN.md)包含 7 份固定提交的真实公开技术文档和 24 道新题；与旧开发集隔离，尚未运行付费测试，也没有真实人工评分。现改为 Jev 匿名自动评审，人工覆盖率0%。
- 私有仓库授权、完整新数据库恢复权限、Docker 和远端 CI 验收仍取决于对应外部环境。这里不将其标记为完成。
- 单用户毕业演示尚无生产认证；团队协作、Webhook 自动同步、IDE 插件与大规模部署不在当前范围。

协作任务的目录、API、预算、兼容策略与页面用法见[多 Agent 说明](docs/MULTI_AGENT.zh-CN.md)。本次验收使用模型替身，不代表真实模型质量。

协作进度持久化的后续改动见 [ADR 0067](docs/adr/0067-durable-agent-progress.zh-CN.md)：已提交的调用预留计数、事件及步骤结果可在中断后读取；保存失败会停止后续调用，同 UUID 重发仍只读。执行仍是同步请求，不自动续跑未完成节点。

协作页面的范围选择见 [ADR 0068](docs/adr/0068-explicit-workflow-scope.zh-CN.md)：提交前预览检索/时间/代码范围，任务详情只读展示已保存的范围；历史问答排除当前代码，代码版本读取失败时不能静默按默认范围执行。

## 文档与目录

`frontend/` 是工作台；`backend/` 包含 API、Worker、迁移和验证脚本；`evaluation/` 保存冻结语料、结果及性能报告；`docs/` 保存设计和验收。

- [后端与命令](backend/README.zh-CN.md) · [前端结构](docs/FRONTEND.md) · [架构](docs/ARCHITECTURE.md)
- [API 契约](docs/API_CONTRACT.md) · [知识模型](docs/KNOWLEDGE_MODEL.md) · [ADR](docs/adr/README.zh-CN.md)
- [实验说明](evaluation/README.md) · [本轮性能](evaluation/performance/2026-10-29-scale/README.zh-CN.md)
- [当前计划](PLANS.zh-CN.md) · [开发路线](docs/ROADMAP.md) · [变更记录](CHANGELOG.zh-CN.md)
- 全项目 Agent 改造（规划中）：[中文方案](docs/PROJECT_AGENT_PLAN.zh-CN.md) · [English plan](docs/PROJECT_AGENT_PLAN.md)
