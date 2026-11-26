# Knowledge Atlas 开发环境配置

2026-11-26 源码预期 schema 为 `20261126_0024`，新增资料归档状态与回答反馈两表；已有库不自动升级。按[备份与恢复](BACKUP_RESTORE.zh-CN.md)先备份并隔离恢复核验，再在 `backend` 用项目虚拟环境运行 `alembic upgrade head`。本轮只在隔离库验证迁移，现有业务库仍需操作者升级。

M5 离线准备（2026-10-31）：已实现冻结的独立20项开发任务、18项验收矩阵、零调用预演、任务/评分导入及统一工程验收命令。M5 整体仍待授权后的真实执行器/夹具重放、真实质量、托管 CI、演示和发布。真实调用为零，无业务迁移，库版本保持0023；历史评估/授权/账本不变。见 [M5 状态与操作说明](PROJECT_ASSISTANT_M5.zh-CN.md)。

M3/M4 当前库版本为 `20261031_0023`。运行 `alembic upgrade head` 前先备份并验证恢复；API 就绪检查不自动迁移。异步 v2/v3 复用独立 assistant runner，不新增依赖/服务。[使用与验证](PROJECT_ASSISTANT_M34.zh-CN.md)。

当前源码/业务 head 为20261031_0021，已在验证备份/隔离恢复和旧表指纹后升级。backend 下启动 `python -m app.assistant_runner`，与 API、来源解析 Worker 分开运行。原生 start-demo.ps1 和可选 Compose 已包含 runner；只有显式 async_v2 新任务可调用已配置模型，不自动重放历史/失败/过期任务。见 [M2 使用/验收](PROJECT_ASSISTANT_M2.zh-CN.md)，下方旧 head 公告为原阶段说明。

M1 源码 head 现为 `20261031_0020`（增量 assistant_tasks），取代下方旧 head 公告。见 [M1 检查](PROJECT_ASSISTANT_M1.zh-CN.md)。未自动升级已安装数据库，就绪检查要求新 head/表。复用 .venv/node_modules，无依赖变更。业务库正常升级前先备份/隔离恢复，再在 backend 运行 `alembic upgrade head`；临时验证使用 `python -m scripts.verify_native`，保留业务版本标记。M1 已通过本地替身/原生/桌面验证，真实质量仍未测量。

离线评审新增 EVALUATION_PROVIDER=openrouter、本地 OPENROUTER_API_KEY、OPENROUTER_MODEL=typesafe/jev-1.14 和 OPENROUTER_TIMEOUT_SECONDS=60，见 [OpenRouter配置](OPENROUTER_EVALUATION.zh-CN.md)。原生 CF 与直连 TypeSafe 字段继续支持，不改业务供应商；无需新增 SDK，默认仍为零调用预演，凭据仅本地保存。

单项目 Agent 协作已接通。更新依赖后使用迁移 `20261029_0019`；新增固定版本 LangGraph，继续使用现有虚拟环境，执行 `.\.venv\Scripts\python.exe -m pip install -e ".[dev,evaluation]"`（backend 目录）。已有数据先备份与隔离恢复核验，再 `alembic upgrade head`。三个角色、四个协作接口和同步/人工审核边界见[实现说明](MULTI_AGENT.zh-CN.md)。


当前源码 head `20261031_0020`；已有库升级前先[备份/隔离恢复](BACKUP_RESTORE.zh-CN.md)。`/health/ready` 同时检查连接与关键结构，失败不会自动迁移。完整启动见[演示](DEMO.zh-CN.md)，能力/验证见[当前验收](OPTIMIZATION_20261029.zh-CN.md)。默认真实 workbench，模型操作显式执行。

## 环境要求

当前需要：

- Git。
- Node.js 22.12 或更高版本（建议 24 LTS）。
- npm 10 或更高版本。
- Python 3.12 或更高版本。
- 本机原生安装的 PostgreSQL 和 pgvector。

本地开发和真实服务验收默认使用用户已有的本机原生安装，Docker/Compose 是可选替代方案。隔离后端测试使用 SQLite，不需要数据库服务。

## 可选的 Neo4j 图谱快照

启动 Neo4j Desktop 实例并复制连接 URI。在后端本地 `.env` 填写以下配置，从 `backend/` 启动或重启 API。如果后端环境缺少 `neo4j` 驱动，在该环境中执行 `python -m pip install -e .`。

```dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=
NEO4J_DATABASE=neo4j
```

按实际实例填写 URI、用户名、密码和数据库名。本地 `.env` 不提交 Git。`DATABASE_URL` 继续使用现有的 PostgreSQL 连接。

1. 调用 `GET /api/v1/health/neo4j`，应返回 `{"status":"up"}`。
2. 调用 `POST /api/v1/projects/{project_id}/graph/neo4j/sync`，应返回写入快照的 `node_count`、`edge_count` 和 `valid_at`。
3. 调用 `GET /api/v1/projects/{project_id}/graph/neo4j`，应返回该快照的节点、边和有效时间。用 `center_id` 和 `depth` 检查邻域遍历。

在项目的「关系图」页点击「筛选」，将「图谱数据源」切到 Neo4j，点击「同步到 Neo4j」，即可看到快照时间和总量。选择节点作为中心，将邻域深度切到二跳，再选中一条关系即可打开原文证据。正式知识变化后再次同步。也可以在 FastAPI 的 `/docs` 发出上述请求。见 [API 契约](API_CONTRACT.md#neo4j-项目快照)和 [ADR 0081](adr/0081-neo4j-project-projection.zh-CN.md)。

## 克隆与检查

```bash
git clone https://github.com/YAX-J/knowledge-atlas.git
cd knowledge-atlas
git status
```

开始实施前阅读 `README.md`、[代理规范](../AGENTS.md) 和 [实施计划](../PLANS.zh-CN.md)。

## 前端环境

```bash
cd frontend
npm install
npm run dev
```

开发服务器默认使用 `http://localhost:5173`。

可用命令：

| 命令 | 用途 |
| --- | --- |
| `npm run dev` | 启动 Vite 开发服务器 |
| `npm run build` | 执行 Vue TypeScript 检查并构建生产资源 |
| `npm run preview` | 预览最近一次生产构建 |

演示图谱及其中的节点追问使用本地 Mock，不需凭据；项目/资料、候选审核、项目图谱和独立证据问答使用真实 API。配置 `VITE_API_BASE_URL` 时可将 `frontend/.env.example` 复制为 `frontend/.env`；`VITE_DATA_SOURCE=graph` 是默认入口，打开真实项目图谱。`api`、`workbench`、`mock` 分别直达资料页、项目总览和独立演示。环境变量变化后重启 Vite。

## 后端环境

从仓库根目录执行：

```bash
cd backend
python -m venv .venv
```

按当前终端类型激活虚拟环境，再安装项目和开发依赖：

```bash
python -m pip install -e ".[dev]"
```

根据 `backend/.env.example` 创建本地环境文件。Windows PowerShell 命令为：

```powershell
Copy-Item .env.example .env
```

使用已有安装工具启动本机 PostgreSQL 服务。创建独立的 `knowledge_atlas` 数据库，或配置其他数据库名。在 `backend/.env` 中将 `DATABASE_URL` 设置为实际本机值；示例使用 localhost 的 5432 端口和占位凭据。

PostgreSQL 必须安装 pgvector。初始迁移执行 `CREATE EXTENSION IF NOT EXISTS vector`，连接账号需要相应权限，或提前由管理员在目标数据库中启用扩展。从 `backend/` 应用迁移并启动 API：

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

常用接口：

| 接口 | 用途 |
| --- | --- |
| `http://localhost:8000/docs` | OpenAPI 交互界面 |
| `GET /api/v1/health/live` | 进程存活检查 |
| `GET /api/v1/health/ready` | PostgreSQL 依赖健康检查 |

在 OpenAPI 界面验证导入时，依次创建项目、上传 UTF-8 Markdown 或 Java 源文件、调用 `POST /api/v1/tasks/{task_id}/run`，并查询 `GET /api/v1/sources/{source_id}/chunks`。也可以在另一个已激活环境的终端中，从 `backend/` 运行 `python -m app.worker`，自动消费上传任务。先应用包含执行租约与图谱表的最新迁移。`python -m app.worker --once` 最多处理一个符合条件的任务后退出。配置、恢复规则、退出码和解析限制见 [后端说明](../backend/README.zh-CN.md)。

验证本机服务配置时，从 `backend/` 运行 `alembic current`，预期版本为 `20261029_0019`；查询 `/api/v1/health/ready`，PostgreSQL 应为 `up`。随后使用真实本地数据库验证项目创建、上传、自动解析、重复复用、重启持久化，以及 Worker/API 竞争。SQLite 测试不能验证原生服务联通、PostgreSQL 锁或 pgvector 距离运算。

如果选择容器方案，从仓库根目录运行 `docker compose up -d --build` 可启动完整环境。Worker 等待 API 应用迁移并通过存活检查后启动。Docker 不是验收前提。

## DeepSeek 候选提取

先应用最新迁移，包括 `review_events` 和正式图谱表。在后端 `.env` 中填写 `DEEPSEEK_API_KEY`（不得放在前端），保留 `DEEPSEEK_BASE_URL=https://api.deepseek.com`，按需设置模型 `DEEPSEEK_MODEL`（默认 `deepseek-flash`）。重启 API 后打开已解析资料，点击“提取候选知识”；只有显式请求时才把该篇资料分块发送到 DeepSeek。核对引用后确认或拒绝，关系必须先确认两端实体；确认会在同一事务内写入受限的实体、关系和证据。Worker 解析不调用模型。测试与浏览器验证使用模拟响应，真实模型调用仍需验收，详见 [后端说明](../backend/README.zh-CN.md#deepseek-候选提取与审核)。

## 语义向量检索

在后端 `.env` 配置 `EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`EMBEDDING_MODEL`；当前 `EMBEDDING_DIMENSIONS` 必须为 `1024`。在项目图谱点击“更新语义索引”后再选择语义模式搜索。实体文本和查询会发送到所配置的服务；知识确认不调用嵌入服务。真实服务与原生 pgvector 路径需单独验收。

## GitHub 快照导入

在资料页选择「同步整个仓库」，页面会自动续传同一固定提交，直到处理完受支持文件。`GITHUB_IMPORT_MAX_FILES` 控制每批 1–50 个文件，默认 50。中断后可继续同一提交，或填写原 ref 再次同步同一提交，已完成的批次会复用。打开 `python -m app.worker` 可在导入期间自动解析。页面关闭会暂停发起新批次。

公开仓库 REST 读取无需凭据。私有仓库或 Review thread 状态只在 `backend/.env` 设置 `GITHUB_TOKEN`，并按所用导入能力授予最小的 Contents、Issues 与 Pull requests 读取权限。保留 `GITHUB_API_BASE_URL=https://api.github.com`、`GITHUB_GRAPHQL_URL=https://api.github.com/graphql`、`GITHUB_API_VERSION=2026-03-10`，仅在需要时调整 `GITHUB_TIMEOUT_SECONDS`。应用迁移 `20261022_0014`，在资料工作台登记 remote 后显式同步默认分支/指定 ref，或导入最近的 Issue/Pull Request 版本。文件请求每批最多导入 50 份支持文件和 20 MiB。工作项请求最多导入 20 项及每项 20 条普通评论，并为每个入选 PR 最多读取 20 条 Review、20 条行级 Review Comment、20 个 Review thread 与每个 thread 20 个评论标识。无令牌时 REST 部分仍会成功，并返回 `review_threads_status=token_required`。同步由用户发起，历史证据继续绑定原提交。

## 前端验证

```bash
cd frontend
npm run build
```

可见界面发生修改时，手动检查：

- 搜索与节点选择。
- 证据展开与关系导航。
- 知识类型筛选。
- 时间回放与详情面板同步。
- 追问状态。
- 候选提取、审核和旧确认补写。
- 项目图谱加载、筛选、一跳/二跳邻域、详情证据，以及空数据和截断状态。
- 关键词/语义模式切换、索引更新、未配置嵌入服务错误和索引覆盖数量。
- 桌面布局（不要求手机浏览器验收）。
- 键盘焦点和面板滚动。

## 后端验证

原生隔离验收：在 `backend/` 运行 `.\.venv\Scripts\python.exe -m scripts.verify_native`（要求 `public` 中已有 pgvector 和 `CREATE SCHEMA` 权限）。脚本显式指定 Alembic 版本表 schema，测试前检查全部测试表确在该 schema，最后只删除自己生成的 schema。不能使用业务资料作为夹具，也不能认为单独设置 `search_path=temp,public` 足够隔离。仅在明确选择真实公开 GitHub 只读验收后加 `--github`，不使用令牌或调用模型。此测试不会升级应用的实际业务 schema。

```bash
cd backend
python -m pytest
```

测试将正式数据库依赖替换为隔离 SQLite 数据库，验证 API 行为与模型集成，但不替代 PostgreSQL 联通检查。

## 本地服务

后端基础阶段采用以下默认配置：

| 服务 | 默认端口 | 用途 |
| --- | --- | --- |
| 前端 | `5173` | Vite 开发服务器 |
| FastAPI | `8000` | REST API（尚无流式响应） |
| PostgreSQL | `5432` | 业务数据和 pgvector |

上述端口是本机服务的默认值；已有数据库使用其他端口时，按实际值配置。API、Worker 和前端分别在本地终端运行。根目录 `compose.yaml` 仍作为可选容器方案保留，后端连接配置可通过环境变量覆盖。

## 环境文件

- 只提交包含变量名和安全开发默认值的 `.env.example` 文件。
- 不得提交 `.env`、令牌、密码、私有地址或生产标识。
- 浏览器可见变量使用 `VITE_` 前缀，并假定用户能够读取其内容。
- 模型服务密钥和 GitHub Token 只保留在后端。

## 换行与格式

- 仓库文本文件使用 UTF-8 编码和 LF 换行。
- JavaScript、TypeScript、JSON、YAML、CSS 和 Markdown 在需要缩进处使用两个空格。
- Python 代码约定使用四个空格缩进。
- 编辑器应遵循根目录的 `.editorconfig` 和 `.gitattributes`。

## 常见问题

### 依赖安装失败

确认 Node 和 npm 版本，然后只删除本地 `frontend/node_modules` 目录并重新安装。不要删除无关仓库文件。

### 5173 端口被占用

使用其他端口运行 Vite：

```bash
npm run dev -- --port 5174
```

### 页面没有真实项目数据

图谱仍读取 `frontend/src/mock/data.ts`。查看真实项目/资料时，打开“我的项目”或“资料来源”、启动后端，并确认 `VITE_API_BASE_URL` 和后端 `CORS_ORIGINS` 与本地地址一致。资料工作台会显示连接错误并提供重试入口。

### 构建产物出现在 Git 状态中

`frontend/dist`、`node_modules`、Vite 缓存和 TypeScript 构建信息应被忽略。添加文件之前检查根目录 `.gitignore`。

### 就绪检查返回 503

PostgreSQL 不可用时，`/api/v1/health/ready` 返回 `degraded`。检查原生服务的运行状态、主机/端口、数据库是否存在，以及 `backend/.env` 中的凭据，再应用最新迁移。只有选择可选 Docker 方案时，才使用 `docker compose ps` 查看容器状态。

## CI 环境边界

`backend` 任务只安装 Python 依赖。模拟 TypeScript 编译器失败测试在临时工作区创建仅用于存在性检查的依赖文件，并替换进程调用，不能依赖 `frontend/node_modules`。SDK/包缺失测试仍须验证启动进程前返回 `SEMANTIC_BACKEND_UNAVAILABLE`。真实编译器验收仍由 `KA_NATIVE_COMPILERS=1` 显式启用，并要求实际 SDK/依赖。

无供应商调用的 API 测试必须为涉及的每个路由显式注入配置。抽取 `configured` 夹具仅配置抽取接口，问答路由须另行注入；不能依靠本机 `.env` 凭据使测试通过，也不能跳过断言或降低后端 90% 覆盖率门槛来绕过 CI 失败。

`.github/workflows/ci.yml` 的 PostgreSQL 服务参数保持为 `--health-cmd "pg_isready -U knowledge_atlas -d knowledge_atlas"`。Actions 将参数交给 Docker 进程，shell 风格的单引号可能使命令拆开，令 `-U` 被误作 Docker 参数。YAML/参数检查与容器实际启动通过是不同验证。推送修复后，应确认新提交的 `backend`、`postgres` 均通过再发布毕业基线；重跑旧提交不会加载本次修复。

## 完成任务前

```bash
git diff --check
git status --short
```

运行相关构建或测试，并报告实际完成的命令。
