# Knowledge Atlas 后端

[English](README.md)

为 Knowledge Atlas 首个持久化与 Markdown 导入功能切片提供服务的 FastAPI 后端。

## 已实现能力

- 存活检查，以及 PostgreSQL/Neo4j 依赖就绪检查。
- 请求 ID、CORS、请求日志和稳定的错误结构。
- 在开发用户边界内创建、列出和查询项目。
- 在同一用户/项目边界内分页查询资料元数据及最新任务。
- 校验并保存 UTF-8 Markdown，记录 SHA-256 内容哈希。
- 创建/查询解析任务，并通过 API 显式执行。
- 可选独立 Worker 自动消费排队任务，提供租约认领、中断恢复和结果写入保护。
- 持久化标题、段落、列表和围栏代码块，保留精确原文、标题路径、哈希和从 1 开始且包含两端的行号范围。
- 同一用户项目内，相同字节的上传复用原来源/任务，即使文件名不同。
- 分页查询分块，安全地重复执行已完成任务或重试失败任务。
- 持久化项目、来源、任务和候选知识记录。

模型抽取、Neo4j 投影、搜索和 Agent 回答尚未实现。

## 环境配置

```bash
python -m venv .venv
# Activate the virtual environment for the current shell.
python -m pip install -e ".[dev]"
```

按当前终端类型激活虚拟环境，再安装依赖。将 `.env.example` 复制为 `.env`，然后从仓库根目录启动 PostgreSQL 和 Neo4j：

```bash
docker compose up -d postgres neo4j
```

应用数据库结构并启动 API：

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

OpenAPI 文档地址为 `http://localhost:8000/docs`。

## 验证解析流程

在交互式 API 文档中依次调用：

1. `POST /api/v1/projects`：创建项目。
2. `POST /api/v1/projects/{project_id}/sources`：上传 UTF-8 `.md` 或 `.markdown` 文件。
3. `POST /api/v1/tasks/{task_id}/run`：同步执行解析。
4. `GET /api/v1/tasks/{task_id}`：查看状态和错误信息。
5. `GET /api/v1/sources/{source_id}/chunks?page=1&page_size=20`：查看证据原文和行号位置。

`GET /api/v1/projects/{project_id}/sources` 用于前端刷新后恢复资料列表及每份资料的最新任务。列表不包含原文，预览内容通过来源详情接口读取。

新任务类型为 `markdown_parsing`；旧版排队的 `knowledge_extraction` 上传任务也只执行解析。成功后任务为 `succeeded`/`parsed`/100，来源变为 `ready`，这不代表已经执行知识抽取。执行失败时返回 HTTP 200，任务状态为 `failed`，错误内容经过脱敏；可调用同一接口重试。重复执行成功任务会返回已有结果；运行中或已取消任务返回 HTTP 409。重复上传响应中返回的是复用任务的当前状态，不一定为 `queued`。

解析器支持 Markdown 的结构化子集：ATX/Setext 标题、段落、列表和围栏代码。其余语法作为文本保留。同一来源与分块边界下，分块 ID 保持稳定。文件字节变化时创建独立来源，不修改既有来源。PostgreSQL 项目行锁串行化重复上传创建；SQLite 不验证这类锁保证。手动接口在 API 进程中解析，自动执行使用下文的 Worker。尚未实现完整 CommonMark 抽象语法树（AST）。

## 自动解析 Worker

先应用最新数据库迁移，然后在另一个已激活后端虚拟环境的终端中运行：

```bash
python -m app.worker
```

Worker 在开发用户的有效项目范围内轮询排队任务和已过期的运行中任务，与 API 共享解析器及持久化流程。上传响应仍为带任务 ID 的 HTTP 202；在页面刷新任务/来源状态即可查看结果。本次实现没有增加浏览器自动轮询，也不会自动重试普通失败任务。

单次处理命令：

```bash
python -m app.worker --once
```

`--once` 最多处理一个任务。退出码 0 表示任务成功或没有可处理工作；1 表示任务处理、恢复次数上限处理或基础设施操作失败。`--user-id <uuid>` 用于将受信任的本地 Worker 显式限定到另一用户，默认使用与 API 相同的临时开发用户 UUID。

| 环境变量 | 默认值 | 行为 |
| --- | --- | --- |
| `TASK_LEASE_SECONDS` | `300` | 固定执行租约，范围 1–86400 秒；API 与 Worker 使用相同值 |
| `TASK_MAX_ATTEMPTS` | `3` | 过期任务达到该累计尝试次数后停止自动恢复，范围 1–100 |
| `WORKER_POLL_INTERVAL_SECONDS` | `2` | 空闲或错误轮次之间的等待时间，大于 0 且不超过 60 秒 |

每次认领都会获得新的内部执行 UUID、递增的尝试次数和过期时间。进程被终止后，另一 Worker 可在租约过期后接手。旧版运行中任务没有租约时，以开始时间为超时基准；开始时间为空时使用最后更新时间。达到次数上限后，任务/来源转为失败，错误码为 `TASK_ATTEMPTS_EXHAUSTED`；超出次数后仍允许明确的手动重试。普通解析失败则保持失败，等待手动重试。

成功与失败更新都必须匹配当前执行 UUID 和运行状态。分块、来源状态和最终任务状态在同一事务中提交。即使被替换的进程稍后恢复，也不能覆盖当前结果。租约没有心跳：仍在运行的解析器超出租约时，可能与接手者同时计算，因此租约应长于正常解析耗时。收到 SIGINT/SIGTERM 后，在当前轮次完成后退出；强制终止依赖租约恢复。

从仓库根目录运行 `docker compose up -d --build` 也会启动 Worker。它等待 API 通过迁移完成后才执行的存活检查。Worker 使用相同后端镜像，不提供 HTTP 端口。Docker 运行以及真实 PostgreSQL 的竞争/恢复行为，仍需在具备 Docker 的机器上验证。

## 测试

```bash
python -m pytest
```

测试使用隔离 SQLite 数据库，覆盖解析、API 行为、失败/重试、访问隔离、保留历史运行任务的迁移升级/回滚、PostgreSQL SQL 离线编译、独立会话之间的 Worker 恢复/写入保护，以及真实单次执行 Worker 子进程。要验证真实 PostgreSQL 和 Neo4j 连接，应在 Docker 环境中调用 `/api/v1/health/ready`。离线编译不能代替真实数据库集成测试。

## 结构

```text
app/
├─ worker.py     # Independent database-backed parsing consumer
├─ api/          # Versioned HTTP routes and dependencies
├─ core/         # Settings, errors, logging, and middleware
├─ db/           # SQLAlchemy base and session factory
├─ models/       # Authoritative persistence models
├─ schemas/      # API request and response models
└─ services/     # Persistence workflows and domain validation
migrations/      # Alembic environment and revisions
tests/           # API behavior tests
```

目录职责：`worker.py` 是独立数据库解析消费者；`api/` 保存版本化路由和依赖；`core/` 保存配置、错误、日志及中间件；`db/` 保存 ORM 基类与会话工厂；`models/` 保存权威持久化模型；`schemas/` 保存接口请求/响应模型；`services/` 保存持久化流程和领域校验；`migrations/` 保存迁移；`tests/` 保存接口行为测试。
