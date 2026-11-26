# Knowledge Atlas

[English](README.md)

Knowledge Atlas 是面向毕业设计的个人技术知识系统，将开发者的技术笔记、代码和仓库历史组织成个人时序知识图谱。首页打开项目图谱。要补充知识，从侧栏进入「项目笔记」，保存 Markdown 修订后点击「分析笔记并提取知识」。核对候选及其原文后确认入图，之后可以从检索结果、历史图谱和问答回溯证据。

前端使用 Vue 3，API 使用 FastAPI，项目数据保存在 PostgreSQL 与 pgvector 中。可选的 Neo4j 图谱投影支持手动同步快照、查看一跳或两跳邻域及定位原文证据。[Neo4j 本机配置](docs/DEVELOPMENT_SETUP.zh-CN.md#可选的-neo4j-图谱快照)

## 当前可用能力

本地带路径上传按路径与内容共同去重：同内容的不同路径分别保留来源，同路径同内容复用已有任务。无路径单文件仍按内容复用，历史缺失路径需重新上传补齐。[来源身份规则](docs/adr/0083-path-aware-source-ingestion.zh-CN.md)

| 环节 | 功能 |
| --- | --- |
| 技术笔记与资料 | 编辑 Markdown 笔记、查看不可变的历史修订，并分析指定修订。支持导入 Markdown、多语言代码、本地文件夹、GitHub 提交快照，以及带版本的 Issue、PR、Review 和讨论线程。 |
| 候选审核 | 按精确原文核对结构化候选。审核建议的事实有效期和主数据库替代关系，再确认入图。 |
| 图谱与治理 | 首页打开关系图，顶部可切换项目。在画布上查看实体、关系、证据和历史快照。回溯替代链和分组演化，管理别名、合并与解除合并、撤回与重新启用，以及检查冲突。 |
| 检索与问答 | 支持关键词、BM25、来源位置 BM25、向量、混合和 RRF 检索。可按历史时点提问，或比较已审核的数据库切换。保存的回答按结论链接到原文证据，并在适用时关联相应关系与有效区间。 |
| 代码分析 | 查看语法结构、静态调用候选以及由编译器解析的 Java、TypeScript 和 Go 声明。路径重复时可选择固定提交或本地资料版本。分析限于静态只读操作，界面会显示扫描上限和截断状态。 |
| 工作台 | 在六块模块中查看实际项目数据，使用命令面板切换工作区，或单独打开 Mock 演示。工作台 URL 可恢复项目、来源、图谱选择、历史时点或问答会话。 |
| Agent 协作 | 提供三个专业角色、两条固定 LangGraph 流程和独立的异步项目助手。任务记录输入范围、调用次数和步骤检查点。修改提案需要显式审批，任务支持取消和手动继续。 |
| 验证工具 | 支持迁移检查、备份与恢复演练、原生 PostgreSQL 验收、离线评测和合成性能测量。 |

项目助手支持整仓后台任务。它按固定的 GitHub 提交分批导入并解析，依据实际选取和读取的文件生成带引用的报告。[仓库导入配置](docs/DEVELOPMENT_SETUP.zh-CN.md#github-快照导入)、[整仓助手任务](docs/PROJECT_ASSISTANT_M34.zh-CN.md#整仓助手任务)

BM25 与来源位置 BM25 每批处理 200 个实体，最多覆盖 50,000 个可见实体。每个实体最多使用 32 条证据和 4,000 字符排序文本。响应返回匹配数和独立的截断标记，RRF 的词法检索也使用同一套 BM25 实现。[ADR 0066](docs/adr/0066-batched-global-lexical-retrieval.zh-CN.md)

Agent 任务保留选定的检索方式、历史时点和代码版本。原有协作流程保存已提交的步骤与尝试计数，中断后可只读查看进度。独立的异步项目助手由专用运行器执行，支持取消和手动继续。[持久化协作进度](docs/adr/0067-durable-agent-progress.zh-CN.md)、[流程输入范围](docs/adr/0068-explicit-workflow-scope.zh-CN.md)

## 本地启动

安装 Python、Node.js 和带 pgvector 的 PostgreSQL，按环境说明填写 `backend/.env`，迁移前备份已有数据库。当前迁移版本为 `20261031_0023`，就绪检查会报告迁移版本落后或缺少必要表和列的数据库。[环境配置](docs/DEVELOPMENT_SETUP.zh-CN.md)、[备份与恢复](docs/BACKUP_RESTORE.zh-CN.md)

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,evaluation]"
cd ..\frontend
npm ci
cd ..
.\scripts\start-demo.ps1 -Seed
```

已有虚拟环境时可以复用。启动与只读状态检查不会发起模型调用，抽取、问答、Agent 执行和语义索引更新需要显式操作。[演示、Worker 与 Docker 命令](docs/DEMO.zh-CN.md)

## 验收状态

- 项目助手的同步和异步流程、笔记修订与审批路径已用本地替身验证。升级至 `0023` 前完成备份和隔离恢复验证，30 张既有业务表内容指纹一致。[M2 报告](docs/PROJECT_ASSISTANT_M2.zh-CN.md)、[M3/M4 报告](docs/PROJECT_ASSISTANT_M34.zh-CN.md)
- M5 已准备冻结的 20 项开发任务、18 项验收矩阵、零调用预演和报告导入流程。真实执行、夹具重放、质量评估及发布仍待完成。[M5 状态](docs/PROJECT_ASSISTANT_M5.zh-CN.md)
- 新回答采用 evidence-claims-v3，后端依据各条结论及其引用计算总体支持状态，历史记录保留原格式。离线评审支持 OpenRouter Jev、直连 TypeSafe Jev 和 Cloudflare Workers AI 原生接口，人工评分覆盖率为 0%。[逐条结论与证据](docs/adr/0075-server-derived-answer-support.zh-CN.md)、[holdout-v3 语料](evaluation/holdout-v3/README.zh-CN.md)、[历史裁判结果](evaluation/results/2026-10-31-holdout-v3-clef-run1/REPORT.zh-CN.md)
- 留出集包含 7 份固定到提交的公开技术文档和 24 道题，与开发集隔离。历史 457 次裁判调用评审的是 v2 输出，v3 的结论校验使用独立的合成开发集。[开发验证](evaluation/development/claim-support-v3/README.zh-CN.md)、[OpenRouter 指南](docs/OPENROUTER_EVALUATION.zh-CN.md)、[Cloudflare 指南](docs/CLOUDFLARE_EVALUATION.zh-CN.md)
- 早期公开实验记录了 84 次模型调用尝试和 61 次嵌入调用尝试。本地替身验证无真实供应商调用。私有仓库访问、完整恢复权限、托管 CI 和 Docker 验收取决于实际环境。[公开实验报告](evaluation/results/2026-10-26-public-v2-run1/REPORT.zh-CN.md)、[此前验收与优化](docs/OPTIMIZATION_20261029.zh-CN.md)
- 单用户演示尚无生产认证。团队协作、Webhook、IDE 扩展和大规模部署暂不在项目范围内。

## 文档与目录

`frontend/` 包含工作台，`backend/` 包含 API、Worker、迁移和验证脚本，`evaluation/` 保存冻结语料、结果及性能报告。

- [后端命令](backend/README.zh-CN.md)、[前端结构](docs/FRONTEND.md)、[系统架构](docs/ARCHITECTURE.md)
- [API 契约](docs/API_CONTRACT.md)、[知识模型](docs/KNOWLEDGE_MODEL.md)、[架构决策记录](docs/adr/README.zh-CN.md)
- [Agent 协作流程](docs/MULTI_AGENT.zh-CN.md)、[评测说明](evaluation/README.zh-CN.md)、[性能测量](evaluation/performance/2026-10-29-scale/README.zh-CN.md)
- [当前计划](PLANS.zh-CN.md)、[开发路线](docs/ROADMAP.md)、[变更记录](CHANGELOG.zh-CN.md)、[历史文档](docs/archive/pre-optimization-20261029/README.md)
- [全项目 Agent 改造方案（规划中）](docs/PROJECT_AGENT_PLAN.zh-CN.md)
