# Knowledge Atlas 后端

整仓助手任务由 `python -m app.assistant_runner` 执行。见[任务和进度契约](../docs/PROJECT_ASSISTANT_M34.zh-CN.md#整仓助手任务)。

可选的 Neo4j 接口用于检查连接、同步单个项目的正式图谱快照，以及通过 Cypher 读取有界邻域。图谱读取同时返回快照时间和全项目总量。见[本机配置](../docs/DEVELOPMENT_SETUP.zh-CN.md#可选的-neo4j-图谱快照)和 [API 契约](../docs/API_CONTRACT.md#neo4j-项目快照)。

M5 离线准备（2026-10-31）：已实现冻结的独立20项开发任务、18项验收矩阵、零调用预演、任务/评分导入及统一工程验收命令。M5 整体仍待授权后的真实执行器/夹具重放、真实质量、托管 CI、演示和发布。真实调用为零，无业务迁移，库版本保持0023；历史评估/授权/账本不变。见 [M5 状态与操作说明](../docs/PROJECT_ASSISTANT_M5.zh-CN.md)。

M2 已通过本地验证，业务库迁至源码 head20261031_0021。`python -m app.assistant_runner` 与解析 Worker 分开启动，--once 最多处理一项 async_v2 排队任务。界面使用异步202的 assistant-task-v2，v1 保留同步200。检查点/尝试/产物、取消及版本绑定显式继续见 [ADR0077](../docs/adr/0077-durable-assistant-execution.zh-CN.md)和[命令/结果](../docs/PROJECT_ASSISTANT_M2.zh-CN.md)。零真实调用，不声称真实质量，未启动 M3–M5。下方 M1/head 公告为各轮历史说明。

项目只读助手 M1 已实现并通过本地替身验证，见[使用/检查](../docs/PROJECT_ASSISTANT_M1.zh-CN.md)和 [ADR0076](../docs/adr/0076-read-only-project-assistant.zh-CN.md)。源码 schema head 现为 `20261031_0020`（仅新增 assistant_tasks），未自动迁移业务库。独立 assistant/tasks 接口和类型化报告不改变旧 agent-runs 或 QuestionRead。本轮零真实调用，M2–M5 仍规划中。下方旧版本公告描述各自原始变更。

离线匿名评审支持 OpenRouter Jev、直连 TypeSafe Jev 和 CF 原生适配。配置 EVALUATION_PROVIDER=openrouter、本地 OPENROUTER_API_KEY、OPENROUTER_MODEL=typesafe/jev-1.14 与 OPENROUTER_TIMEOUT_SECONDS=60，旧凭据保留。本轮零真实调用，人工评分覆盖率0%。见 [OpenRouter命令](../docs/OPENROUTER_EVALUATION.zh-CN.md)、[CF](../docs/CLOUDFLARE_EVALUATION.zh-CN.md) 和 [Jev](../docs/JEV_EVALUATION.zh-CN.md)。

[ADR 0075](../docs/adr/0075-server-derived-answer-support.zh-CN.md) 已实现 `evidence-claims-v3`：模型只返回 confidence、claims、missing_information，后端按所有条目状态计算 API 的 supported；逐条引用、缺失信息、预算与项目边界保持严格。v2 和平铺历史按原保存值读取/重放，不重算或调模型；v2 不作为新输出回退。使用独立虚构开发用例验证结构与兼容性，未测量 v3 真实质量。冻结 v2 实验/账本/评分和 schema head `20261029_0019` 不变，人工覆盖率0%。

单项目 Agent 协作已接通。更新依赖后使用迁移 `20261029_0019`；新增固定版本 LangGraph，继续使用现有虚拟环境，执行 `.\.venv\Scripts\python.exe -m pip install -e ".[dev,evaluation]"`（backend 目录）。已有数据先备份与隔离恢复核验，再 `alembic upgrade head`。三个角色、四个协作接口和同步/人工审核边界见[实现说明](../docs/MULTI_AGENT.zh-CN.md)。

[English](README.md)

当前说明见本轮验收与 ADR 0060–0063；迁移 head `20261029_0019`。旧日期检查点已归档，不再叠加在当前说明顶部。 [验收 / Acceptance](../docs/OPTIMIZATION_20261029.zh-CN.md)

## 本轮上下文与运行检查

协作读取现从已保存请求白名单投影 `scope`：检索/时间、代码开关/策略、快照/本地版本 ID。协作页面可选择这些既有参数，将已保存范围与新草稿分开；历史问题排除当前代码，元数据读取错误不触发按默认范围的付费回退。不新增迁移或改变默认模式。见 [ADR 0068](../docs/adr/0068-explicit-workflow-scope.zh-CN.md)。

协作任务现会在执行回调前提交无原文的事件和模型/工具/嵌入预留计数，续租有效归属并保存校验后的步骤结果（ADR 0067）。同步 POST 等待时 GET 可观察进度；后续步骤失败保留先前结果。进度保存拒绝待提交业务写入，无法保存时停止后续调用。同 UUID 重发仍只读，进程中断不授权自动付费续跑。本轮无需迁移，head 保持 `20261029_0019`。见[持久化与限制](../docs/adr/0067-durable-agent-progress.zh-CN.md)。

BM25/来源位置 BM25 使用 `mixed-bm25-v2` / `mixed-bm25-source-v2`：每批 200 个实体按键分页，在最多 50,000 个作用域内可见实体上统一统计和打分；每实体最多 32 条排序证据、每条 2000 字符、排序文本 4000 字符。`lexical.matched_count` 与 `results_truncated` 区分 Top K 结果和扫描/文本省略；RRF 词法路使用同一实现。不新增供应商请求、迁移、持久化索引或正式图谱写入。见 [ADR 0066](../docs/adr/0066-batched-global-lexical-retrieval.zh-CN.md)。旧实验分数不是 v2 测量。

`GET /sources/{id}/analysis-contexts` 只读列出可选提交/重复路径版本；显式调用分析接受 snapshot_id 或重复 version_ids，返回实际 context。所有策略使用固定原路径、有界正文和用户/项目/仓库隔离。别名长度按规范化值再次校验；合并链/解除检索有回归。就绪状态检查实际 schema0019 与关键表/列。

索引规划原始归属证据每500实体读取，不改变哈希或付费规则。规模复现：`python -m scripts.benchmark_scale --output ../output/scale-new-run.json --repeats 20`；仅自有临时原生schema，无供应商。API字段见[契约](../docs/API_CONTRACT.md)，测量边界见[报告](../evaluation/performance/2026-10-29-scale/README.zh-CN.md)。

## 已实现能力

- 存活检查，以及 PostgreSQL 依赖就绪检查。
- 请求 ID、CORS、请求日志和稳定的错误结构。
- 在开发用户边界内创建、列出和查询项目。
- 解析/查询项目范围的本地文件夹身份，规范化 GitHub HTTPS/SSH remote，保存 provider ID 与 Commit 快照，可选关联本地仓库，并在同一用户/项目边界内显式增量导入有界的 GitHub Markdown/Java 快照，以及带版本的 Issue/Pull Request 和 PR Review 活动 Markdown 来源。
- 校验并保存 UTF-8 Markdown 与 Java 源码，记录 SHA-256 内容哈希、可空仓库身份和规范化仓库内相对路径。
- 创建/查询解析任务，并通过 API 显式执行。
- 可选独立 Worker 自动消费排队任务，提供租约认领、中断恢复和结果写入保护。
- 持久化 Markdown 标题/段落/列表/围栏代码和 Java 代码/注释/类型/方法分块，保留精确原文、结构路径、哈希和从 1 开始且包含两端的行号范围。顶层类型注解随类型保存，方法外的纯注释行单独成块。
- 同一用户项目、可空仓库和来源类型内，相同字节的上传复用原来源/任务，即使文件名不同。
- 分页查询分块，安全地重复执行已完成任务或重试失败任务。
- 派生有界只读 Java 大纲，提供稳定的类型/字段/方法符号、未限定名或 `this.` 同文件调用提示，以及依据包与导入解析的仓库内跨文件 `extends`/`implements` 目标和显式类型的直接类型、字段、参数、直属局部变量接收者方法调用；派生结构不会提升到正式图谱。
- 可为 Java、Python、JavaScript/JSX、TypeScript/TSX、Go、C/C++ 或 C# 显式运行一轮有界 Agent 调用分析，只处理同仓库声明候选。候选 ID 与精确源码行证据由后端校验；空候选不调用供应商，全部结果均不持久化。
- 持久化项目、来源、任务和候选知识记录。
- 确认候选时在审核事务内写入受限的 PostgreSQL 实体、关系和证据，支持稳定 UUID、端点提升、幂等重复和旧确认重放。
- 提供只读项目图谱、实体详情和关系详情接口，按用户/项目/时间过滤，限制节点与边数量，并返回后端计算的行号。
- 为 GitHub 导入来源派生固定 Commit 的文件 URL，并为正式图谱/搜索/问答证据派生精确行号 URL，同时保留与供应商无关的 `project://` 定位符。

已实现显式 DeepSeek 候选提取、审核与正式图谱提升、项目关键词/语义向量/一跳图关系混合检索，以及同步证据问答。语义索引使用显式重建操作和可配置的 OpenAI-compatible Embeddings 服务；真实服务/原生 pgvector 搜索冒烟已通过，包含关系的代表性召回和真实回答质量仍待验收。已实现人工身份整理和有界会话历史；通用多轮规划仍不在范围。

## 环境配置

### 演化审核与原生验收

使用时间/演化/治理面板前先应用 head `20261029_0019`。跨来源建议与抽取候选分离；仅人工确认才可关闭旧有效期并开始新有效期。历史保留证据，治理只读；不能回溯提升前或定时至未来。见 [ADR 0039](../docs/adr/0039-reviewed-knowledge-evolution.zh-CN.md)。

在 `backend/` 运行 `.\.venv\Scripts\python.exe -m scripts.verify_native`，在临时 schema 验证迁移/API/竞争/Worker。要求配置的原生 PostgreSQL、已在 `public` 安装 pgvector，以及 `CREATE SCHEMA` 权限。脚本显式限定 Alembic 版本表 schema，测试前检查本地表，最后只删除自己生成的 schema。既有业务资料不是测试数据。`--github` 另允许真实只读公开 petclinic 导入/检索/重复/Commit 追溯验收，不调用模型或使用 GitHub 令牌。普通 `pytest` 跳过这些显式验收；不验证模型/嵌入质量或私有令牌。

`GITHUB_IMPORT_MAX_FILES` 设置每批文件预算（1–50，默认 50）。整仓同步按固定提交沿保存的快照续传。匿名公开 GitHub 文件优先从固定提交的原文地址读取，并校验 Git blob 哈希。解析 Worker 可在导入期间处理队列；GitHub 限流可能暂停同步，已保存批次可继续。

```bash
python -m venv .venv
# Activate the virtual environment for the current shell.
python -m pip install -e ".[dev]"
```

按当前终端类型激活虚拟环境，再安装依赖。将 `.env.example` 复制为 `.env`，将 `DATABASE_URL` 填为本机原生服务的实际配置。示例凭据只是开发占位值，不代表你已有数据库的凭据。API 和 Worker 均从 `backend/` 使用同一环境文件。

启动本机已安装的 PostgreSQL，创建独立的 `knowledge_atlas` 数据库，或在配置中使用其他数据库名。PostgreSQL 必须安装 pgvector：初始迁移执行 `CREATE EXTENSION IF NOT EXISTS vector`，因此当前账号需要相应权限，或提前由管理员在目标数据库中启用扩展。不要求 Docker。

应用数据库结构并启动 API：

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

OpenAPI 文档地址为 `http://localhost:8000/docs`。

## 验证解析流程

在交互式 API 文档中依次调用：

1. `POST /api/v1/projects`：创建项目。
2. 文件夹导入先用根目录名调用 `POST /api/v1/projects/{project_id}/repositories/resolve`，再通过 `POST /api/v1/projects/{project_id}/sources` 逐份上传注册表支持的 UTF-8 Markdown/代码文件，同时提交 `repository_id` 和规范化的仓库内 `relative_path`。单文件上传同时省略两者。还可通过 `POST /api/v1/projects/{project_id}/repositories/resolve-github` 登记 GitHub HTTPS/SSH remote，再显式调用 `POST /api/v1/projects/{project_id}/repositories/{repository_id}/sync-github` 导入有界文件快照，或调用 `POST /api/v1/projects/{project_id}/repositories/{repository_id}/import-github-work-items` 导入最近的 Issue/Pull Request 版本。
3. `POST /api/v1/tasks/{task_id}/run`：同步执行解析。
4. `GET /api/v1/tasks/{task_id}`：查看状态和错误信息。
5. `GET /api/v1/sources/{source_id}/chunks?page=1&page_size=20`：查看证据原文和行号位置。

`GET /api/v1/projects/{project_id}/sources` 用于前端刷新后恢复资料列表及每份资料的最新任务。列表包含可空的仓库 ID/名称、`relative_path` 和固定 Commit 的 `git_url` 元数据但不包含原文，预览内容通过来源详情接口读取。本地来源的 Git URL 为 `null`。同一可空仓库内相同字节复用时保留首次来源的文件名和相对路径。

Markdown 任务使用 `markdown_parsing`，Java 任务使用 `code_parsing`；旧版排队的 `knowledge_extraction` 上传任务也只执行 Markdown 解析。成功后任务为 `succeeded`/`parsed`/100，来源变为 `ready`，这不代表已经执行知识抽取。执行失败时返回 HTTP 200，任务状态为 `failed`，错误内容经过脱敏；可调用同一接口重试。重复执行成功任务会返回已有结果；运行中或已取消任务返回 HTTP 409。重复上传响应中返回的是复用任务的当前状态，不一定为 `queued`。

Markdown 解析器支持 ATX/Setext 标题、段落、列表和围栏代码。

Java 静态导入扩展可通过显式 `import static Type.method` 和通配 `Type.*`，把未限定调用链接到同仓库其他 ready 来源中的可访问静态方法。已有成员名称保守阻止导入回退，即使参数数量不符；显式静态导入阻止通配回退。跨文件响应使用 `receiver="import static"`，保留原方法 ID/行号、歧义和既有上限。限定 `this`/`super` 调用不会使用导入。这是有界扩展，不是完整 Java 访问/重载求解，见 [ADR 0030](../docs/adr/0030-java-static-import-calls.zh-CN.md)。

Java 结构/调用分析 V1 为只读派生能力，限定同仓库最多 100 份 ready 来源、相关原文累计 20 MiB；返回稳定类型/字段/方法、同文件调用、继承目标和跨文件方法候选。词法作用域包括普通块/if/else/while/try/catch/finally、带花括号的增强/传统 for 及资源 try 体。头部调用省略，头部绑定随主体结束；未知 `var`、数组元素和多异常 catch 参数只遮蔽、不猜测类型。完整的方法体局部 `var value = Type.factory(...)` 可在按实参数量筛选后使用所有候选一致的、可访问仓库内静态工厂返回类型，见 [ADR 0036](../docs/adr/0036-bounded-java-static-factory-var-receivers.zh-CN.md) 及下文未限定名调用扩展。

工厂推断也支持通过当前/继承静态成员或显式/通配静态导入完成的未限定名 `factory(...)` 初始化。成员名称优先，即使参数数量不符；私有静态成员仅支持在精确当前类型中以未限定名调用。所选导入所有者缺失、成员查找不完整、非静态/未知/冲突返回、类型限定名被遮蔽或方法类型参数返回时，局部变量保持未知。链式、实例和 `this`/`super` 限定仍不在本切片范围内。见 [ADR 0037](../docs/adr/0037-unqualified-java-factory-receivers.zh-CN.md) 及 `tests/test_java_factory_receivers.py`。

相同工厂规则也适用于带花括号的传统 for 单声明及资源 try 单/多声明头部中的 `var`。头部与方法体声明按源码顺序处理，资源名称只从前向后影响初始化表达式的遮蔽。绑定只延续至主体与嵌套作用域，在 catch/finally 或相邻块前结束；头部调用边继续省略。未知初始化仍只遮蔽、不回退。见 [ADR 0038](../docs/adr/0038-java-header-factory-receivers.zh-CN.md) 及 `tests/test_java_header_factories.py`。

方法候选按实参数量（含可变参数）筛选；无法可靠计数时保留候选。有界继承查找去重菱形路径并抑制相同继承签名，保留同参数数量的类型重载和重复来源版本歧义；继承的未限定/`this`/`super` 调用定位到原方法符号。不继承私有方法、构造器和接口静态方法；继承环或单次 256 节点遍历预算触顶报告截断。不承诺运行时分派、完整访问/类型检查、通用工厂/链式推断、重新赋值数据流或外部 classpath 求解，见 [V1 能力与验收边界](../docs/JAVA_ANALYSIS_V1.zh-CN.md)。

数组字段/参数/局部变量及可变参数保持未知接收者绑定，阻止元素方法猜测和同名字段/类型回退。覆盖方括号两种位置及多维数组；含数组类型实参的标量泛型接收者仍为标量。工厂返回类型在调用文件的导入环境中保持已解析身份，涵盖默认包类型和重复版本。解析器与 API 回归见 `tests/test_java_receiver_safety.py`。

同一来源与分块边界下，分块 ID 保持稳定。文件字节变化时创建独立来源，不修改既有来源。PostgreSQL 项目行锁串行化仓库解析与重复上传创建；SQLite 不验证这类锁保证。手动接口在 API 进程中解析，自动执行使用下文的 Worker。一次 GitHub 同步读取一个显式快照，最多导入 50 份支持文件，累计预算 20 MiB，保存 Commit/文件来源信息，并从上一快照复用未变化 blob。完整 tree 会报告重命名与删除；远端删除的文件仍保留为不可变历史来源，并解析到最后一次非删除快照的 Commit 链接。另一个显式操作会把最近更新的最多 20 个 Issue/Pull Request 及每项最多 20 条普通评论导入为 Markdown，并按 provider ID 与 `updated_at` 保存不可变版本；每个入选 PR 还会生成独立的 Review 活动快照，最多包含 20 条 Review 与 20 条行级 Review Comment，并按内容摘要复用。配置令牌后，快照还会包含最多 20 个 GraphQL Review thread 与每个 thread 20 个评论标识，包括当前解决状态和解决者；无令牌时 REST 导入仍成功并报告缺少该补充。精确解决事件时间、附件、reaction、完整分页、Webhook、轮询和来源/知识失效尚未实现。

再次使用既有同步操作时，GitHub 同步会重试同 Commit 的不完整快照。成功资料/任务仅在用户/项目/仓库和来源类型一致、解析任务兼容时复用。tree/文件/字节截断、大小跳过或来源/任务引用缺失与不兼容，会触发新的有界快照；成功的历史快照保持不变。完整快照（包括确定性的空文件/编码/路径跳过）仍直接返回。50 文件上限仍是选择上限，不是分页；重复尝试不保证导入整个仓库。不完整 tree/文件集合不推断重命名。Markdown/Java 后缀变化会创建或复用正确类型的来源，不会重命名不兼容来源。见 [ADR 0031](../docs/adr/0031-recoverable-typed-github-snapshots.zh-CN.md)。

`GET /api/v1/projects/{project_id}/sources/{source_id}/chunks/{chunk_id}` 在未归档项目及用户/项目/来源范围内读取精确已保存分块，返回既有分块形状和从 0 开始的 `position`，不要求解析任务仍存在，不扫描全部分块页。缺失或不匹配返回 404 `SOURCE_CHUNK_NOT_FOUND`，项目不可访问沿用项目 404。用于本地图谱/搜索/问答原文跳转，无需新迁移或供应商调用，见 [ADR 0035](../docs/adr/0035-exact-evidence-source-navigation.zh-CN.md)。

### 代码符号定位

`GET /api/v1/projects/{project_id}/code-symbols?q=save&kind=method` 检索 ready Java 来源，不调用模型、不写入知识。可选 `repository_id` 收窄项目范围；`limit` 默认 50（1–100）。按本地大纲限定名或来源路径进行不区分大小写的字面子串匹配。最多扫描 100 份来源、20 MiB 原文及每份 200 个符号，优先考虑较早来源。`scanned_source_count`、`matched_count`、`truncated` 描述有界扫描，不是全项目总数。结果保留大纲 ID/行号、来源/仓库/任务元数据、可空的 `chunk_id`/从 0 开始的 `chunk_position`，以及固定 Commit/行号的 `git_url`。不代表超出上限的分页或编译器求解，见 [ADR 0032](../docs/adr/0032-bounded-code-symbol-search.zh-CN.md)。

### 已保存的提交证据

`GET /api/v1/projects/{project_id}/repositories/{repository_id}/snapshots` 查询已保存元数据，新增可空 `commit_source_id` / `commit_task_id`。在同一路径追加 `/{snapshot_id}/commit-source` 后 `POST`（无请求体），返回 HTTP 200，包含 `snapshot_id`、`source_id`、`task_id`、当前 `status`、`reused` 和规范 `git_url`。它把保存的 SHA、UTC 时间与提交说明渲染为确定性 Markdown，复用仓库范围导入；不请求 GitHub/模型，也不启动解析或抽取。相同字节跨 ref/改名复用来源，不跨仓库复用。沿用大小限制和作用域 404；无效 SHA 返回 409 `SNAPSHOT_COMMIT_INVALID`。提交证据打开 `/commit/{sha}`，不追加 `#L`，本地行号只描述 Markdown，不定位 patch。先应用迁移 `20261022_0014`，见 [ADR 0033](../docs/adr/0033-saved-commit-evidence-sources.zh-CN.md)。

`GET /api/v1/projects/{project_id}/repositories/{repository_id}/snapshots/{snapshot_id}/files?page=1&page_size=20` 查询保存的逐文件来源（每页 1–100）。只读本地记录，按路径/UUID 排序，包含删除与跳过项；`total` 是记录数，不是完整仓库覆盖率。可空来源/任务跳转会校验作用域和类型，不加载原文正文。文件 URL 固定所选提交并使用当前规范 remote；删除路径不生成该提交中的文件链接，仍可打开保留的本地资料。除现有快照 schema `20261022_0014` 外无需新迁移或供应商请求。见 [ADR 0034](../docs/adr/0034-snapshot-file-provenance.zh-CN.md)。

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

Docker Compose 是可选替代方案：从仓库根目录运行 `docker compose up -d --build` 也会启动 Worker。它等待 API 完成迁移并通过存活检查，使用相同后端镜像，不提供 HTTP 端口。默认验收使用本机原生 PostgreSQL；用户已报告 PostgreSQL 17/pgvector、本机启动、上传解析、重复复用、重启保留和自动解析通过；PostgreSQL 竞争/恢复故障注入仍待专项验证，可选容器启动也尚未验证。

## DeepSeek 候选提取与审核

审核或语义索引前先执行 `alembic upgrade head`，当前预期版本为 `20261029_0019`。只在后端 `.env` 中配置：

```dotenv
DEEPSEEK_API_KEY=your_local_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_TIMEOUT_SECONDS=120
EXTRACTION_MAX_INPUT_CHARS=60000
EMBEDDING_API_KEY=your_embedding_key
EMBEDDING_BASE_URL=https://your-provider.example/v1
EMBEDDING_MODEL=your-1024-dimension-model
EMBEDDING_DIMENSIONS=1024
GITHUB_TOKEN=optional_read_only_token
GITHUB_API_BASE_URL=https://api.github.com
GITHUB_GRAPHQL_URL=https://api.github.com/graphql
GITHUB_API_VERSION=2026-03-10
GITHUB_TIMEOUT_SECONDS=30
```

默认模型依据 [DeepSeek 官方接口文档](https://api-docs.deepseek.com/)。适配器使用 JSON 输出和非思考模式，仍由后端自行校验 Schema。公开 REST 导入可不设置 `GITHUB_TOKEN`；私有仓库与 GraphQL Review thread 状态需要只放在后端的令牌，并按所选导入授予最小的 Contents、Issues 与 Pull requests 读取权限。空值或纯空白令牌视为未配置。`GITHUB_GRAPHQL_URL` 默认指向 GitHub.com，可为兼容测试端点独立调整；remote 登记仍只支持 GitHub.com。修改配置后重启 API。本地环境文件已补齐缺失的空值/默认配置字段，真实密钥不得提交或放进前端配置。

解析资料后，在候选区域显式请求提取，才会把该篇资料分块发送到 DeepSeek。`POST /api/v1/sources/{source_id}/extract` 同步执行，`GET /api/v1/sources/{source_id}/extraction` 读取任务状态。解析 Worker 不调用模型。单次默认最多 100 个分块、序列化输入 JSON 60000 字符、50 个实体、100 个关系、8192 输出 token 和 1 MiB 响应；超限会拒绝，不会静默截断，请拆分来源。

输出必须符合 Schema，关系必须引用本次实体，摘录必须逐字存在于同一来源的分块中。整批结果全部通过或全部拒绝。按来源/提示版本复用成功提取，修改模型配置后也沿用成功结果；当前没有强制重新提取功能。失败调用需手动重试，中断可在租约到期后重试（至少采用配置的任务租约或模型超时加 60 秒），旧执行不能覆盖新结果。不自动重试模型请求，以免重复计费；超时或中断的调用可能已经到达服务商。

通过 `GET /api/v1/projects/{project_id}/reviews` 和 `POST /api/v1/reviews/{review_id}/resolve` 查询与审核候选。允许确认/拒绝，确认前可修改名称和摘要；关系两端实体必须先确认。相同决策重复提交幂等，当前不支持改判、合并、撤销或重新提取。迁移 `0004` 增加操作者、时间及前后值审计记录；迁移 `0005` 增加正式图谱表，回滚会删除图谱记录和证据，但保留来源、候选与审核事件。

确认候选时，在同一条审核事务内写入正式实体、关系和证据。语义向量由之后的显式索引操作生成，不影响确认事务。实体合并和消歧仍待开发；真实 DeepSeek 回答质量与嵌入服务都需单独验收。

## 项目图谱

`GET /api/v1/projects/{project_id}/graph` 返回当前用户有效项目的 `nodes`、`edges` 和 `truncated`。可选参数为 `center_id`、`depth`（1 或 2）、`types`（逗号分隔的实体类型）、`valid_at` 和 `limit`（1–200，默认 100）；边上限为 500。可见条件为未归档、当前或已保存历史生效区间包含查询时间，再按该时刻投影身份（ADR 0056）。

`GET /api/v1/knowledge/entities/{entity_id}` 返回实体、最多 100 条直接关系，以及带原始文件名、`project://` URI、可空 GitHub URL、引用、标题路径和后端计算行号的证据。仓库文件链接固定到 Commit 精确行号；Issue/Pull Request 链接打开规范会话，行号则定位导入的 Markdown 快照。`GET /api/v1/knowledge/relationships/{relationship_id}` 返回关系及其证据。画布坐标不属于接口，布局由前端负责。

2026-10-17 验证：后端 100 项测试通过；前端构建及桌面/手机浏览器流程通过，使用隔离 SQLite 和模拟抽取。本机 PostgreSQL 17.10 + pgvector 在临时 schema 中通过迁移升级/回退/再升级、图谱和证据读取，以及每个候选四个独立会话的并发重复确认。临时 schema 已删除。之后已将业务 schema 升级至 `20261017_0005` 修复缺失图谱表，真实图谱/候选/资料/搜索读取均返回 200。真实 DeepSeek 质量、原生数据库的浏览器验收及 Worker/API 竞争和恢复仍需单独检查。

2026-10-18 验证：102 项后端测试、前端生产构建及桌面/手机真实页面走查通过；业务数据库完成 `0005 → 0006 → 0005 → 0006`，确认 pgvector `0.8.7`、`vector(1024)` 列和余弦运算可用。测试使用模拟嵌入；当前 `.env` 未配置嵌入服务，真实语义召回质量尚未验收。

2026-10-18 后续验证：加入混合检索后，全量测试增至 104 项并全部通过。已配置的真实嵌入服务与原生 PostgreSQL/pgvector 在浏览器中返回 7 条已索引混合结果，组成得分和证据可见；该项目没有已确认关系，因此非零图关系解释由自动测试覆盖，尚未在这组冒烟数据中出现。

2026-10-18 最终验证达到 109 项后端测试全部通过。问答聚焦测试覆盖支持性回答、越界引用拒绝、无证据时不调用回答模型、缺少配置、供应商失败和请求校验；前端生产构建及桌面/390 px 浏览器走查通过。可见回答使用浏览器本地拦截响应，因此真实 DeepSeek 回答质量仍未验收。

## 关键词、语义向量与图关系混合搜索

`GET /api/v1/projects/{project_id}/search` 支持 `mode=keyword`、`mode=vector` 和 `mode=hybrid`。关键词模式保留名称、摘要、证据的确定性加权；向量模式先用当前配置模型生成查询向量，再通过 pgvector 余弦距离对已索引正式实体精确排序；混合模式按固定 `0.3/0.4/0.3` 权重融合关键词、向量和可见一跳关系，并返回归一化分量与关系解释。三种模式都支持 `types`、带时区的 `valid_at`、`top_k`，并返回最多 3 条原文证据。

语义、混合搜索或问答前调用 `POST /api/v1/projects/{project_id}/embeddings/rebuild`。它将正式实体类型、名称、摘要及证据发送到配置的嵌入服务，保存到 `knowledge_embeddings`；模型和内容哈希未变化时不重复生成。该操作与知识确认事务分离。当前向量固定 1024 维，未建立近似索引。见 [ADR 0009](../docs/adr/0009-explicit-semantic-index.zh-CN.md) 与 [ADR 0010](../docs/adr/0010-explainable-hybrid-graph-retrieval.zh-CN.md)。

## 证据问答

`POST /api/v1/projects/{project_id}/questions` 接受 1–200 字的问题和可选的带时区 `valid_at`。接口同步执行有界混合检索，只把选定的正式证据交给 DeepSeek，校验严格 JSON 与引用归属，并只返回实际引用的证据、实体和检索统计。没有证据时直接返回确定性拒答，不调用回答模型。响应不持久化；问答历史、流式输出和多轮编排留待后续。见 [ADR 0011](../docs/adr/0011-synchronous-evidence-grounded-questions.zh-CN.md)。

## 测试

```bash
python -m pytest
```

测试使用隔离 SQLite 数据库，覆盖解析、API 行为、失败/重试、访问隔离、保留历史运行任务的迁移升级/回滚、PostgreSQL SQL 离线编译、独立会话之间的 Worker 恢复/写入保护、真实单次执行 Worker 子进程、候选审核、正式图谱写入、旧确认重放和有界图谱查询。要验证真实 PostgreSQL 连接，应针对配置的本机原生服务调用 `/api/v1/health/ready`；验收时 PostgreSQL 依赖应为 `up`。离线编译不能代替真实数据库集成测试。

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
