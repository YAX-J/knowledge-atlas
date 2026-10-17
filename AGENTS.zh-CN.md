# Knowledge Atlas 仓库代理规范

[English](AGENTS.md)

本文为 `AGENTS.md` 的中文版本，两种版本同步维护。AI 编码代理的仓库规范入口仍为 `AGENTS.md`。

## 项目用途

Knowledge Atlas 是面向单人开发者的毕业设计项目。它将技术笔记、代码、项目文档和 Git 记录组织成个人时序知识图谱，并通过有证据支撑的检索来回答问题。

仓库当前包含可交互的 Mock 演示图谱、接入真实 API 的项目/资料工作台、FastAPI 持久化接口，支持手动执行或可选数据库 Worker 的 Markdown 解析与租约恢复，显式 DeepSeek 候选提取、证据校验和带审计记录的审核，以及将已确认候选写入受限、只读的 PostgreSQL 项目图谱。项目关键词检索与证据展示已实现。实体消歧、语义检索和 Agent 回答尚未实现。真实 DeepSeek 验收应与模拟响应测试区分。

## 修改代码前阅读

只阅读与当前任务相关的文档，优先从以下文件开始：

- `README.md`：项目范围和当前状态。
- `docs/ARCHITECTURE.md`：组件边界和数据归属。
- `docs/FRONTEND.md`：现有 Vue 前端。
- `docs/KNOWLEDGE_MODEL.md`：实体、关系、证据和时序规则。
- `docs/API_CONTRACT.md`：前后端边界草案。
- `PLANS.md` 和 `docs/ROADMAP.md`：当前阶段与后续工作。
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
- 双语文档、ADR、变更记录 → `.agents/skills/ka-docs-sync/SKILL.md`

索引：`.agents/skills/README.md`。技能描述流程，本文件的规则仍然优先。行为或工作流变化时同步更新对应技能。

## 仓库结构

- `frontend/`：Vue 3、TypeScript、Vite、Element Plus 和 Mock 数据。
- `backend/`：FastAPI、SQLAlchemy 模型、Alembic 迁移和接口测试。
- `docs/`：架构、前端、知识模型、接口、路线、环境配置和 ADR 文档。
- `.github/`：Issue 与 Pull Request 模板。
- `.agents/skills/`：仓库级代理技能，记录具体任务流程。
- `compose.yaml`：本地 PostgreSQL/pgvector、API 和解析 Worker 服务。
- `backend/app/worker.py`：独立的数据库解析消费者，复用后端模型和服务。
- 尚未创建的规划内容：提示词资源和实验数据集。

## 必须遵守的领域规则

- 每条生成的知识和回答都必须能够追溯到来源证据。
- 大模型可以提出候选内容，但不得直接写入权威业务表。
- PostgreSQL 是当前唯一数据库，也是业务数据与图谱存储的事实来源。暂缓引入 Neo4j；仅在实测需求证明有必要时再引入图数据库，并记录 ADR。
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
- 组件通过 props 接收数据，通过事件表达用户意图。在确实需要路由或状态库之前，页面编排保留在 `App.vue`。
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

前端发生修改时，在 `frontend/` 中运行：

```bash
npm run build
```

后端发生修改时，在 `backend/` 中运行：

```bash
python -m pytest
```

可见界面发生修改时，还要在真实浏览器中以桌面和手机宽度验证受影响流程，检查键盘焦点、空状态、内容裁切和面板滚动。

每次修改均需：

- 运行 `git diff --check`。
- 确认没有意外跟踪生成文件、构建产物、依赖或密钥。
- 只报告实际运行的检查。没有执行测试时，不得声称测试通过。
- 已有测试框架时添加有针对性的测试，不得用手动检查替代测试。

## 文档维护职责

- 只有安装方式、仓库结构、项目状态或主要能力改变时才更新 `README.md`。
- API 结构改变时更新 `docs/API_CONTRACT.md`。
- 实体、关系、证据或时序语义改变时更新 `docs/KNOWLEDGE_MODEL.md`。
- 重要架构决策记录在 `docs/adr/`。
- 在明确创建发布版本之前，变化记录保留在 `CHANGELOG.md` 的 `Unreleased` 小节。
- 明确标记规划中的行为，不得让文档暗示 Mock 行为已经是正式能力。
- 文档存在 `.zh-CN.md` 配套版本时，在同一次修改中同步两种语言，并保持语言切换链接有效。翻译必须保留命令语法、标识符，以及已完成/规划中的状态区别。

## 范围与安全

- 本地开发和验收默认使用用户本机安装的 PostgreSQL（含 pgvector）。Docker Compose 是可选方案，不得作为真实服务验证的前提。
- 优先选择能够推进“Markdown 到有证据回答”流程的最小纵向功能切片。
- 除非用户明确要求，否则不增加团队协作、复杂权限、IDE 插件或大规模部署。
- 用户已授权在每轮完成后进行本地提交，按下方工作流执行。推送、发布、部署、轮换凭据或修改外部服务仍需要单独的明确授权。
- 工作区已有未提交改动时，保留与本任务无关的用户修改。
- 不得将真实私有仓库内容、访问令牌或个人密钥加入测试夹具、截图、日志或文档。

## 每轮完成后提交

- 除非用户明确提出其他要求，否则每轮对话完成修改后，必须在最终回复前提交已完成的改动。这是持续有效的本地提交授权，不再重复询问确认。
- 提交前运行与修改相适应的检查、同步相关文档并审查暂存差异。只提交属于已完成工作的改动，保留无关的用户修改。
- 提交信息简洁说明最终行为；适当时将独立改动分成聚焦的提交。
- 本轮没有文件修改时，不创建空提交。
- 必需检查失败或无法创建提交时，保留工作并报告失败，不得声称工作已完成或提交成功。
- 最终回复中报告提交哈希，以及仍未提交的改动。本地提交不代表获得远端推送授权。

## 完成标准

只有所需行为已经实现、相关验证通过、文档同步、完成的改动按上述流程提交，并说明剩余限制时，才算完成。完成路线中的一个阶段，不代表获得自动开始下一阶段的授权。
