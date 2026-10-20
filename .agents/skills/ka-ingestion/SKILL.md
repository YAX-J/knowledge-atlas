---
name: ka-ingestion
description: Knowledge Atlas 的 Markdown/Java 上传、去重、解析、分块与解析 Worker。修改导入校验、分块规则、任务状态或租约恢复时使用。触发词：upload, ingestion, source, chunk, parse, worker, lease, 上传, 解析, 分块, 去重.
---

# 上传、解析与 Worker

这条链路负责把 Markdown 和 Java 源码变成“可引用、带行号”的原文分块。实现：`services/ingestion.py`、`services/markdown.py`、`services/java_source.py`、`services/parsing.py`、`app/worker.py`。

## 何时使用

- 修改上传校验、去重规则、来源状态。
- 修改 Markdown/Java 分块边界、行号、结构路径。
- 修改手动执行、Worker 轮询、租约、重试。
- 排查“上传后没有分块”“重复上传建了两条”“任务一直 running”。

## 上传规则

- 接受 `.md` / `.markdown` / `.java`（大小写不敏感），其他扩展名返回 415 `UNSUPPORTED_SOURCE_TYPE`。
- `source_type` 省略时由后缀推断；填写时必须与 `markdown` / `java` 推断值一致，否则 422 `SOURCE_TYPE_INVALID`。
- 默认最大 10 MiB（`MAX_UPLOAD_BYTES`），超出 413 `SOURCE_TOO_LARGE`。
- 必须 UTF-8，否则 422 `SOURCE_ENCODING_INVALID`；空内容 422 `SOURCE_EMPTY`。
- 保存原文、字节数、SHA-256、媒体类型和规范化的 `original_name`（去掉路径）；文件夹上传还保存本地来源仓库 UUID 与最长 1024 字符的规范化仓库内 `relative_path`。
- 上传成功始终返回 HTTP 202，响应里的 `status` 可能是 `queued`、`running`、`succeeded`、`failed`、`cancelled`。
- 桌面端文件夹最多提取 50 份支持文件，先按项目、`local_folder` 与根目录名幂等解析仓库，再顺序调用单文件接口并提交仓库 UUID 和剥离根目录名后的相对路径；单份失败不回滚其他成功请求。
- 仓库可登记规范化 GitHub HTTPS/SSH remote，或把 remote 关联到本地文件夹仓库；登记本身不联网、不克隆。随后可显式同步默认分支或指定 ref：按稳定路径顺序导入最多 50 份非空 UTF-8 Markdown/Java blob，单份沿用 `MAX_UPLOAD_BYTES`，累计最多 20 MiB，并逐份复用本节的去重与解析任务链路。部分文件无效时跳过，不回滚已成功项；tree/数量/总字节触顶时返回截断。

## 去重语义

- 作用域：同一用户、同一项目、同一可空仓库、同一来源类型。
- 键：文件字节的 SHA-256（与文件名、相对路径无关）。
- 先对项目行加锁，再查已有来源 + 解析任务；命中则复用原 `source_id` 和 `task_id`，保留首次上传的文件名与相对路径。
- 内容变化、换仓库或换项目 → 新来源，不自动建立版本/`SUPERSEDES` 关系。
- 复用返回的是任务**当前**状态，不要假设一定是 `queued`。

## GitHub 快照同步

- `POST /projects/{project_id}/repositories/{repository_id}/sync-github` 只接受已登记 `provider=github` 的仓库。
- `ref` 省略时读取默认分支，也可指定 branch、tag 或 commit SHA；每次有效同步保存 Commit/tree 元数据与逐文件 blob/status 快照。同一 ref 连续解析到相同 Commit 时直接返回已有快照，不再请求 tree/blob。
- 使用 GitHub repository、commit、recursive tree 和 blob REST 端点。公开仓库无需令牌；私有仓库令牌只放后端 `GITHUB_TOKEN`，建议仅授予 Contents read。
- 单份跳过码包括 `SOURCE_EMPTY`、`SOURCE_ENCODING_INVALID`、`SOURCE_PATH_INVALID`、`SOURCE_TOO_LARGE` 和 `GITHUB_IMPORT_TOTAL_SIZE_EXCEEDED`。
- 后续 Commit 优先按“路径 + blob SHA”复用未变化文件；已知 blob 可复用既有来源/任务而不重新下载。旧路径消失且相同 blob 只出现在一个新路径时记录 `renamed`；完整 tree 中消失的旧路径记录 `deleted`。截断快照禁止推断删除。
- GitHub repository `id` 持久化为 provider ID；远端 owner/name 变化时在同一仓库记录上更新规范坐标。重命名/删除只记录同步事实，不破坏性删除历史来源、分块或正式证据。
- 不实现不可变 Git URL 证据、Issue/PR、Webhook、定时同步或自动失效传播。

## 解析规则

`parse_markdown(content, source_id=...)`：

- 保留原始换行，分块内容是来源的精确切片。
- 支持 ATX/Setext 标题、段落、列表、围栏代码；主题分隔线按段落保留；其余语法当文本。
- `kind`：`heading`、`paragraph`、`list`、`code`。
- `position` 从 0 开始；`start_line`/`end_line` 从 1 开始且包含两端。
- `heading_path` 是当前标题栈；标题块自身也包含在路径中。
- 分块 ID：`uuid5(source_id, f"{start_line}:{end_line}:{kind}:{sha256(content)}")`，同一来源同一内容稳定，不同来源不共享。
- 不支持完整 CommonMark AST；不要声称支持所有语法。

`parse_java(content, source_id=...)`：

- 保留精确整行原文，识别顶层类型和常规直接成员方法。
- `kind`：类型外为 `code`，方法外的纯注释行为 `comment`，类型片段为 `type`，方法为 `method`。
- 顶层类型正上方连续的注解行归入 `type`；方法注解归入 `method`。
- 路径：类型为 `[type]`，方法为 `[type, method]`。
- 屏蔽注释、字符串、字符和文本块时保持偏移/换行；不提供完整 AST、嵌套类型语义、重载签名或调用图。

`GET /sources/{source_id}/code-structure`：

- 仅用于已解析 Java 来源，按需从不可变原文派生，不持久化。
- 返回稳定的类型/常规字段/方法符号（最多 200）及未限定名或 `this.` 的同文件调用（最多 500）。
- 在同仓库最多 100 份 `ready` Java 来源内，按显式导入、同包和通配导入解析顶层类型的跨文件 `extends`/`implements`；未归属仓库的旧来源只在未归属集合内解析。相关来源原文累计读取上限 20 MiB，返回目标来源路径、行号及 `resolved`/`ambiguous`。
- 同一范围内还解析直接类型限定调用及当前顶层类型直接字段上的 `field.method()` / `this.field.method()`；最多返回 500 个相关方法和 500 条跨文件调用，并包含目标路径和行号。唯一方法名为 `resolved`，同名/重载为 `ambiguous`。
- 不解析局部变量、参数、链式接收者、参数类型、重载选择、继承分派、依赖注入或动态调用。
- 派生关系不是正式知识，不能绕过候选提取与审核写入图谱。

## 任务状态

| 阶段 | 任务 | 来源 |
| --- | --- | --- |
| 上传 | `queued` / `uploaded` | `uploaded` |
| 认领 | `running` / `parsing` | `processing` |
| 成功 | `succeeded` / `parsed` / 100 | `ready` |
| 失败 | `failed` / `parsing` / `SOURCE_PARSE_FAILED` | `failed` |
| 多次中断 | `failed` / `TASK_ATTEMPTS_EXHAUSTED` | `failed` |

`ready` 只表示解析完成，不表示已抽取或已确认。

## 手动执行

`POST /api/v1/tasks/{task_id}/run`：

- `queued` / `failed`：原子认领后执行。
- `succeeded`：直接返回原结果，不重复建分块。
- `running` / `cancelled`：409 `TASK_NOT_RUNNABLE`。
- 解析异常：HTTP 200，任务 `failed`，来源 `failed`，不保留不完整分块，可重试。
- Markdown 支持 `markdown_parsing` 和旧版 `knowledge_extraction`；Java 支持 `code_parsing`。来源与任务类型不匹配时返回 409 `TASK_TYPE_UNSUPPORTED`。

## Worker

`python -m app.worker [--once] [--user-id UUID]`：

- 只消费当前用户、未归档项目、Markdown/Java 来源及对应的 `markdown_parsing`/`knowledge_extraction`/`code_parsing` 任务。
- 条件：`queued`，或 `running` 且租约过期（无租约时按 `started_at`/`updated_at` 判断）。
- 认领写入新 `execution_id`、递增 `attempt_count`、租约截止时间。
- 成功/失败更新都必须匹配 `execution_id` 和 `running`；旧执行不能覆盖新结果。
- 过期且 `attempt_count >= TASK_MAX_ATTEMPTS` → `failed` + `TASK_ATTEMPTS_EXHAUSTED`，需手动重试。
- 普通解析失败不自动重试。
- `--once`：处理至多一个任务；退出码 0 = 成功或无工作，1 = 失败。
- 收到 SIGINT/SIGTERM 在当前轮次结束后退出；没有心跳。

## 重解析与证据冲突

解析成功时会先删除该来源的现有分块再写入。`knowledge_evidence.chunk_id` 是 `RESTRICT`，一旦候选已提升为正式证据，删除分块会失败，任务转为 `failed`。

- 当前不支持破坏性重解析；不要删除有正式证据的来源/分块。
- 需要修正原文时，先评估是否新增来源（内容变化本来就会新建来源），而不是覆盖旧来源。
- 增量更新（只重算变化分块）尚未实现。

## 测试配方

```bash
cd backend
python -m pytest tests/test_sources.py tests/test_parsing.py tests/test_source_list.py tests/test_worker.py tests/test_github_import.py
```

重点覆盖：

- 扩展名、大小、编码、空文件、`source_type` 校验。
- 同一可空仓库中的相同字节重复上传复用；不同仓库、不同项目或不同内容新建。
- 分块数量、类型、标题路径、行号、哈希、ID 稳定性。
- 手动执行幂等、失败重试、运行中 409。
- Worker 租约接手、旧执行写入被拒、次数上限、`--once` 子进程退出码。
- GitHub 默认/指定 ref、同 Commit 短路、路径/blob 复用、重命名/删除、provider ID 仓库改名、快照历史、tree/文件/字节截断、raw blob 流式大小限制和供应商错误脱敏。
- 正式证据存在时重解析失败（如已实现相应测试）。

## 完成检查

- [ ] 上传边界与错误码未变松。
- [ ] 去重仍限定在用户 + 项目 + 可空仓库 + 来源类型 + SHA-256。
- [ ] 分块仍是原文精确切片，行号仍从 1 开始。
- [ ] 租约 fencing 没有被绕过。
- [ ] 文档（`API_CONTRACT.md`、后端 README、ADR 0003/0004）已同步。
- [ ] 实际运行的测试与结果已记录。
