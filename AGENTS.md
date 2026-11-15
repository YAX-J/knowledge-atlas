# Knowledge Atlas 仓库代理规范

M5 离线准备（2026-10-31）：已实现冻结的独立20项开发任务、18项验收矩阵、零调用预演、任务/评分导入及统一工程验收命令。M5 整体仍待授权后的真实执行器/夹具重放、真实质量、托管 CI、演示和发布。真实调用为零，无业务迁移，库版本保持0023；历史评估/授权/账本不变。见 [M5 状态与操作说明](docs/PROJECT_ASSISTANT_M5.zh-CN.md)。

当前状态（2026-10-31）：M3–M4 已实现不可变笔记修订和有范围的项目动作，已有内容与正式知识修改需精确人工审批（ADR0078–0079）。源码/业务库版本为 `20261031_0023`，升级前31表备份及隔离恢复通过，30张旧业务表内容指纹保持一致。参见 [M3/M4 实现与验证](docs/PROJECT_ASSISTANT_M34.zh-CN.md)。M5 继续延期；本轮仅用本地替身，真实供应商调用为零，冻结评估/账本和人工0%保持原状。

历史 M2 验收快照（当前状态以上方 M3/M4 为准）：assistant-task-v2 排队202，v1 保留同步200。业务库/源码 head 为20261031_0021，备份/隔离恢复和旧表指纹核验通过。只有 app.assistant_runner 消费显式 async_v2 queued，不自动重放/重排失败、过期、未知或历史任务。调用前尝试预留、逐模型/单项工具检查点、类型化产物及精确修订/检查点绑定的继续回执生效。未知模型结果须确认，预算/角色次数累计；取消/租约 fencing 拒绝迟到发布。固定运行时/模型/端点/工具契约及来源哈希；GET/轮询/事件/产物仅读取。M3–M5、写入和真实质量仍未实现/测量，冻结实验/账本和人工0%保持，沿用用户已选择的 Agent 验证。

2026-10-31最新：ADR0075 的新模型输出使用 evidence-claims-v3，顶层只含 confidence/claims/missing_information，总体 supported 由后端计算。模型生成总体/平铺字段、漏引或越界引用仍拒绝，保持预算、不重试/回退。v2 和平铺记录按保存值读取/重放，不重算或调用模型。使用独立虚构 evaluation/development/claim-support-v3 用例，不以冻结holdout/失败输出来调提示词。本轮仅离线验证；历史 v2 失败/分数、输入、授权/账本不变，人工0%，v3真实质量未测量。旧真实授权均已用尽。见 docs/adr/0075-server-derived-answer-support.zh-CN.md；下文旧说明为历史。

当前离线评审支持 OpenRouter Jev、直连 TypeSafe Jev 和 CF 原生适配（ADR0073）。用户要求新增 OpenRouter 兼容，本开发轮零真实调用；保留人工评分覆盖率0%、正式人工审核、冻结输入/结果/holdout 和历史账本。独立凭据、显式供应商授权、调用前落盘预留，不重试/回退/续跑；校验 OpenRouter 发布/快照 ID 及实际模型，批内漂移即停止，保留环境代理。见 docs/OPENROUTER_EVALUATION.zh-CN.md。CF 第三方 Jev 统一路由仍不属于原生 CF 适配。

2026-10-29 当前状态：应用库与迁移 head 为 `20261029_0019`；受限 Agent 与持久化人工审核流程见 ADR 0064–0065 和[实现说明](docs/MULTI_AGENT.zh-CN.md)。保持单项目，规范模块为 agents/、workflows/、tools/、analysis/、llm/，迁移过的 services 保留导入别名。三个角色共享有界尝试预算，正式入图只由人工审核触发。同 UUID 重发、只读恢复和审核后继续不得自动重复付费请求。ADR0061 的不可变版本和原生编译器边界继续适用。公开付费累计仍为 84 模型 /61 嵌入，本次重构零新增；评估支持 OpenRouter Jev、直连 TypeSafe 或 CF 原生匿名评审、人工覆盖率0%，holdout-v3 不可调参。此前测量作为[历史验收](docs/OPTIMIZATION_20261029.zh-CN.md)保留。

离线词法检索新增显式 `mode=bm25`（ADR 0044），与默认字面关键词、固定混合模式分开。必须保留用户/项目/类型/时间隔离及扫描/文本上限，返回截断信息，不把分数当作可回答性。语义空索引在本地配置校验后跳过查询嵌入。新实验单独版本化，2026-10-25 结果是开发诊断，不是独立盲测或人工质量分。

多语言解析 V1 已将原 Markdown/Java 导入链路扩展到 Python、JavaScript/JSX、TypeScript/TSX、Go、C、C++、C#，贯通单文件/文件夹、GitHub 文件、Worker、精确原文分块、大纲及符号检索。默认解析只做语法结构，显式提示语法错误，不执行代码、不调用模型也不自动入图；独立显式 Agent 操作可按 ADR 0041 对后端给出的同仓库跨文件调用候选分类。旧 GitHub 完整同提交快照可显式 `rescan=true` 发现新语言。修改时读 `docs/MULTILANGUAGE_PARSING.zh-CN.md`、ADR 0040 与 ADR 0041；注册表 `services/source_languages.py`，语法解析器 `services/code_source.py`；下文 Java 确定性规则仍仅适用 Java。


本文件是 AI 编码代理的仓库规范入口。

## 项目用途

Knowledge Atlas 是面向单人开发者的毕业设计项目。它将技术笔记、代码、项目文档和 Git 记录组织成个人时序知识图谱，并通过有证据支撑的检索来回答问题。

仓库当前包含可交互的 Mock 演示图谱、接入真实 API 且分别支持桌面端 Markdown/Java 单文件与仓库范围文件夹上传及相对路径持久化的项目/资料工作台、规范化 GitHub remote 身份与 provider ID，以及带持久化 Commit 快照和增量 blob 复用的显式有界 ref 同步、从快照派生并固定到 Commit 的 GitHub 文件/行号证据 URL、显式有界且带版本的 Issue/Pull Request 与 PR Review 活动 Markdown 导入及令牌支持的 GraphQL Review thread 当前状态快照、Markdown 解析、有界本地 Java 解析及仓库范围结构/调用分析 V1（词法/头部作用域、继承候选和保守参数数量筛选）、租约恢复、DeepSeek 候选抽取和带审计审核、确认后写入 PostgreSQL 图谱、带证据的关键词/语义向量/一跳图关系混合检索，以及带引用校验的同步证据问答与持久化项目会话。权威 GitHub Review thread 事件时间、自动轮询/Webhook、远端删除的破坏性传播、完整构建/运行时代码语义、自动身份决策和通用多轮规划仍不在范围；派生代码结构不是正式知识。真实 GitHub/私有令牌验收、DeepSeek 质量与代表性原生 pgvector 验收应与模拟测试区分。

显式调用分析接口覆盖全部已登记代码语言，默认 single_step，可选 tools：授权快照上最多 4 轮模型、8 次只读工具（ADR 0043）。它只能对后端给出的同仓库声明候选分类，后端校验输出 ID 与精确调用/声明行。接口同步、非持久化，不由解析 Worker 消费，也不写正式图谱。这不代表已实现完整跨文件语义或多轮规划 Agent，见 ADR 0041。

## 修改代码前阅读

只阅读与当前任务相关的文档，优先从以下文件开始：

- `README.md`：项目范围和当前状态。
- `docs/ARCHITECTURE.md`：组件边界和数据归属。
- `docs/FRONTEND.md`：现有 Vue 前端。
- `docs/KNOWLEDGE_MODEL.md`：实体、关系、证据和时序规则。
- `docs/API_CONTRACT.md`：前后端边界草案。
- `PLANS.zh-CN.md` 和 `docs/ROADMAP.md`：当前阶段与后续工作。
- `docs/adr/`：已接受的架构决策。

除非用户明确要求核对差异，否则不要将仓库外的 Word 文档视为比上述文件更新的依据。

## 仓库技能

具体任务流程放在 `.agents/skills/`。开始工作前先读对应 `SKILL.md`：

- 抽取、提示词、证据校验 → `.agents/skills/ka-extraction/SKILL.md`
- 审核、写入正式图谱、图谱查询 → `.agents/skills/ka-review-promotion/SKILL.md`
- 模型、Alembic、数据结构 → `.agents/skills/ka-migrations/SKILL.md`
- 验证与完成判定 → `.agents/skills/ka-verify/SKILL.md`
- 上传、解析、Worker → `.agents/skills/ka-ingestion/SKILL.md`
- Vue 工作台与图谱界面 → `.agents/skills/ka-frontend-workspace/SKILL.md`
- 文档、ADR、变更记录 → `.agents/skills/ka-docs-sync/SKILL.md`

索引：`.agents/skills/README.md`。技能描述流程，本文件的规则仍然优先。行为或工作流变化时同步更新对应技能。

## 仓库结构

- `frontend/`：Vue 3、TypeScript、Vite、Element Plus 和 Mock 数据。
- `backend/`：FastAPI、SQLAlchemy 模型、Alembic 迁移和接口测试。
- `docs/`：架构、前端、知识模型、接口、路线、环境配置和 ADR 文档。
- `.github/`：Issue 与 Pull Request 模板。
- `.agents/skills/`：仓库级代理技能，记录具体任务流程。
- `compose.yaml`：本地 PostgreSQL/pgvector、API 和解析 Worker 服务。
- `backend/app/worker.py`：独立的数据库解析消费者，复用后端模型和服务。
- `evaluation/`：冻结合成语料、金标准问题、仅依据语料的审核标注和版本化实验结果；独立初始化/基线命令位于 `backend/scripts/`（ADR 0042）。提示词和供应商现位于 `app/llm`，实验数据保持冻结。

## 必须遵守的领域规则

- 每条生成的知识和回答都必须能够追溯到来源证据。
- 大模型可以提出候选内容，但不得直接写入权威业务表。
- PostgreSQL 是业务数据与图谱存储的事实来源。可选的 Neo4j 接入按 ADR 0081 提供显式同步、可重建的项目快照。
- 实体、关系和证据使用稳定的业务 UUID。不得通过 API 暴露数据库内部 ID。
- `valid_from` 和 `valid_to` 是属性，不是图关系类型。
- 时序替代方向为 `new knowledge -[:SUPERSEDES]-> old knowledge`，即新知识指向旧知识。
- 即使当前应用是单用户，也必须保留 `user_id` 和 `project_id` 边界。
- 新增实体或关系类型时必须修改知识模型；涉及架构影响时还需要 ADR。

## 前端约定

- 使用 Vue 3 Composition API 和 `<script setup lang="ts">`。
- 保持 TypeScript 严格模式，除非集成边界确实需要，否则避免使用 `any`。
- 可复用的领域类型放在 `frontend/src/types.ts`。
- 演示数据放在 `frontend/src/mock/`，不要在组件中混入 Mock 记录。
- 组件通过 props 接收数据，通过事件表达用户意图。App 连接项目/导航/共享写锁；组合模块管理请求生命周期（ADR 0062）。路由状态归 useWorkspaceRoute，不通过重放写入恢复位置。
- 保持技术制图风格：冷色纸面背景、深青色文字、玫红选中状态、琥珀色项目强调，以及克制的动效。
- 保持键盘可操作、焦点可见、减少动态效果支持和响应式布局。
- 不要求后端返回画布坐标。布局属于前端或视图偏好。

## 后端约定

- 使用 FastAPI 和带类型的请求、响应模型。
- 分离 API、领域逻辑、持久化和外部模型集成。
- 大模型输出必须先通过明确的 Schema 校验，再持久化。
- 导入和知识持久化操作必须具备幂等性。
- 密钥只放在环境变量或密钥管理服务中。环境文件只提交 `.env.example`。
- 数据库迁移尽可能采用增量变更，并支持回滚。
- 请求处理函数保持简洁，持久化与校验流程放在 `backend/app/services/`。
- 在有意识地引入身份认证替代方案之前，保留临时开发用户边界。

## 验证

执行任何验证前，Agent 必须先向用户提供具体的步骤、命令、前置条件和预期结果，再询问由用户还是 Agent 执行。在用户选择由 Agent 执行前，不得运行测试、构建、迁移升级/回滚检查、服务冒烟、浏览器走查、`git diff --check` 或同类验证命令。用户已在当前请求中明确选择的，不再重复询问。

本轮验证按用户选择的执行方进行。在选定检查通过或用户反馈结果前，将改动标记为“待验证”；不得因为完成静态代码审查就暗示检查已经通过。

前端发生修改时，建议在 `frontend/` 中运行：

```bash
npm run build
```

后端发生修改时，建议在 `backend/` 中运行：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

可见界面发生修改时，还要包含真实浏览器桌面端走查步骤，覆盖键盘焦点、空状态、内容裁切和面板滚动；不要求手机宽度测试或手机截图。

每次修改均需：

- 将 `git diff --check` 纳入建议的验证步骤。
- 确认没有意外跟踪生成文件、构建产物、依赖或密钥。
- 只有 Agent 在用户选择后实际执行了检查，或用户反馈了结果时，才报告检查结果；否则明确标注“待验证”。
- 已有测试框架时添加有针对性的测试，不得用手动检查替代测试。

## 文档维护职责

- 只有安装方式、仓库结构、项目状态或主要能力改变时才更新 `README.md`。
- API 结构改变时更新 `docs/API_CONTRACT.md`。
- 实体、关系、证据或时序语义改变时更新 `docs/KNOWLEDGE_MODEL.md`。
- 重要架构决策记录在 `docs/adr/`。
- 在明确创建发布版本之前，变化记录保留在 `CHANGELOG.zh-CN.md` 的 `Unreleased` 小节。
- 明确标记规划中的行为，不得让文档暗示 Mock 行为已经是正式能力。
- 根目录 `README.md` 使用英文，其余项目文档使用中文。更新功能时同步相关文档，保留命令语法、标识符、链接以及已完成和规划中的状态区别。

## 范围与安全

- 本地开发和验收默认使用用户本机安装的 PostgreSQL（含 pgvector）。Docker Compose 是可选方案，不得作为真实服务验证的前提。
- 优先选择能够推进“Markdown 到有证据回答”流程的最小纵向功能切片。
- 除非用户明确要求，否则不增加团队协作、复杂权限、IDE 插件或大规模部署。
- 用户已授权在每轮完成后进行本地提交，按下方工作流执行。推送、发布、部署、轮换凭据或修改外部服务仍需要单独的明确授权。
- 工作区已有未提交改动时，保留与本任务无关的用户修改。
- 不得将真实私有仓库内容、访问令牌或个人密钥加入测试夹具、截图、日志或文档。

## 每轮完成后提交

- 除非用户明确提出其他要求，否则每轮对话完成修改后，必须在最终回复前提交已完成的改动。这是持续有效的本地提交授权，不再重复询问确认。
- 提交前准备与修改相适应的检查步骤并由用户选择执行方，同步相关文档并审查暂存差异。只提交属于已完成工作的改动，保留无关的用户修改。
- 提交信息简洁说明最终行为；适当时将独立改动分成聚焦的提交。
- 本轮没有文件修改时，不创建空提交。
- 必需检查失败或无法创建提交时，保留工作并报告失败，不得声称工作已验证或提交成功。
- 最终回复中报告提交哈希，以及仍未提交的改动。本地提交不代表获得远端推送授权。

## 完成标准

所需行为与聚焦测试已经实现、文档已同步、完成的改动按上述流程提交、验证步骤与执行方选择已记录并说明剩余限制时，视为“实现完成”。只有 Agent 执行的检查通过，或用户反馈其执行的检查通过后，才能称为“已验证”。完成路线中的一个阶段，不代表获得自动开始下一阶段的授权。
