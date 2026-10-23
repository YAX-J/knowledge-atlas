# Knowledge Atlas 开发环境配置

多语言解析新增固定 Tree-sitter/语言 wheel。在 `backend` 运行 `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"` 更新依赖；不新增服务或迁移，安装后离线解析。详见[语言范围](MULTILANGUAGE_PARSING.zh-CN.md)。

[English](DEVELOPMENT_SETUP.md)

本文说明当前仓库的环境配置，并为后续后端开发保留约定。除非另有说明，命令从仓库根目录执行。

## 环境要求

当前需要：

- Git。
- Node.js 20 或更高版本。
- npm 10 或更高版本。
- Python 3.12 或更高版本。
- 本机原生安装的 PostgreSQL 和 pgvector。

本地开发和真实服务验收默认使用用户已有的本机原生安装，Docker/Compose 是可选替代方案。隔离后端测试使用 SQLite，不需要数据库服务。

当前依赖已移除 Neo4j，图谱存储使用 PostgreSQL，见 [ADR 0005](adr/0005-postgresql-only-storage.zh-CN.md)。已有本地环境文件中的 `NEO4J_*` 配置可以删除；配置加载器会忽略这些旧字段。

## 克隆与检查

```bash
git clone https://github.com/YAX-J/knowledge-atlas.git
cd knowledge-atlas
git status
```

开始实施前阅读 `README.md`、[代理规范](../AGENTS.zh-CN.md) 和 [实施计划](../PLANS.zh-CN.md)。

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

默认的演示图谱和问答使用本地 Mock 数据，不需要数据库或模型凭据。项目/资料导航、候选审核和项目图谱使用真实 API。需要修改 `VITE_API_BASE_URL` 时，将 `frontend/.env.example` 复制为 `frontend/.env`；设置 `VITE_DATA_SOURCE=api` 可默认打开资料工作台。修改环境变量后重启 Vite。这不会将演示图谱或问答切换为真实数据。

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

验证本机服务配置时，从 `backend/` 运行 `alembic current`，预期版本为 `20261023_0015`；查询 `/api/v1/health/ready`，PostgreSQL 应为 `up`。随后使用真实本地数据库验证项目创建、上传、自动解析、重复复用、重启持久化，以及 Worker/API 竞争。SQLite 测试不能验证原生服务联通、PostgreSQL 锁或 pgvector 距离运算。

如果选择容器方案，从仓库根目录运行 `docker compose up -d --build` 可启动完整环境。Worker 等待 API 应用迁移并通过存活检查后启动。Docker 不是验收前提。

## DeepSeek 候选提取

先应用最新迁移，包括 `review_events` 和正式图谱表。在后端 `.env` 中填写 `DEEPSEEK_API_KEY`（不得放在前端），保留 `DEEPSEEK_BASE_URL=https://api.deepseek.com`，按需设置模型 `DEEPSEEK_MODEL`（默认 `deepseek-flash`）。重启 API 后打开已解析资料，点击“提取候选知识”；只有显式请求时才把该篇资料分块发送到 DeepSeek。核对引用后确认或拒绝，关系必须先确认两端实体；确认会在同一事务内写入受限的实体、关系和证据。Worker 解析不调用模型。测试与浏览器验证使用模拟响应，真实模型调用仍需验收，详见 [后端说明](../backend/README.zh-CN.md#deepseek-候选提取与审核)。

## 语义向量检索

在后端 `.env` 配置 `EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`EMBEDDING_MODEL`；当前 `EMBEDDING_DIMENSIONS` 必须为 `1024`。在项目图谱点击“更新语义索引”后再选择语义模式搜索。实体文本和查询会发送到所配置的服务；知识确认不调用嵌入服务。真实服务与原生 pgvector 路径需单独验收。

## GitHub 快照导入

可选 `GITHUB_IMPORT_MAX_FILES=50` 接受每次新扫描 1–50 文件。下调可减少匿名请求并明确生成未完成快照；之后扩大预算显式同步会复用已有 blob。完整缓存的元数据可能超过下调后的预算，但不会额外下载 blob。仍可能遇到限流；显式公开验收使用 30，不代表完整仓库覆盖。

公开仓库 REST 读取无需凭据。私有仓库或 Review thread 状态只在 `backend/.env` 设置 `GITHUB_TOKEN`，并按所用导入能力授予最小的 Contents、Issues 与 Pull requests 读取权限。保留 `GITHUB_API_BASE_URL=https://api.github.com`、`GITHUB_GRAPHQL_URL=https://api.github.com/graphql`、`GITHUB_API_VERSION=2026-03-10`，仅在需要时调整 `GITHUB_TIMEOUT_SECONDS`。应用迁移 `20261022_0014`，在资料工作台登记 remote 后显式同步默认分支/指定 ref，或导入最近的 Issue/Pull Request 版本。文件请求最多导入 50 份支持文件和 20 MiB；工作项请求最多导入 20 项及每项 20 条普通评论，并为每个入选 PR 最多读取 20 条 Review、20 条行级 Review Comment、20 个 Review thread 与每个 thread 20 个评论标识。无令牌时 REST 部分仍会成功，并返回 `review_threads_status=token_required`。两条链路都不会 clone、轮询、接收 webhook 事件历史、自动失效历史证据或自动同步。

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
- 桌面和手机布局。
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
| FastAPI | `8000` | REST 与流式 API |
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

## 完成任务前

```bash
git diff --check
git status --short
```

运行相关构建或测试，并报告实际完成的命令。
