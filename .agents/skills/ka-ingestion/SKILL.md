---
name: ka-ingestion
description: Knowledge Atlas 的 Markdown/Java 上传、去重、解析、分块与解析 Worker。修改导入校验、分块规则、任务状态或租约恢复时使用。触发词：upload, ingestion, source, chunk, parse, worker, lease, 上传, 解析, 分块, 去重.
---

# 上传、解析与 Worker

## 多语言 V1 扩展（ADR 0040）

下述 Markdown/Java 通用链路现同时接受 Python、JavaScript/JSX、TypeScript/TSX、Go、C、C++、C#；完整扩展名以 `services/source_languages.py` 和 `docs/MULTILANGUAGE_PARSING.zh-CN.md` 为准。Worker/手动解析使用该注册表的任务兼容关系，新语言复用 `code_parsing`。`services/code_source.py` 用固定 Tree-sitter wheel 生成整行精确分区（每块最多 120 行）、最多 200 符号/100,000 节点访问，并额外派生最多 200 个本地调用点；截断与语法错误分开，原文始终保留。`code-structure` 增加 `language/has_syntax_errors`；符号检索扩展全部代码、命中增加 `language`。默认结构读取仍不调用模型；`POST /sources/{source_id}/agent-call-analysis` 是独立显式操作，只从同仓库兼容语言族的 ready 来源建立候选，输出不持久化、不自动入图。旧完整 GitHub 同提交快照可显式 `rescan=true` 重读 tree，仍复用兼容 blob 并保留预算；默认缓存不变。测试增加 `tests/test_multilanguage.py` 与 `tests/test_code_agent.py`。安装依赖后再验收，不用语言伪装 Markdown，也不跨来源类型复用任务。

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

- `GITHUB_IMPORT_MAX_FILES` 为后端每次新扫描预算，1–50、默认 50；与硬上限取最小。下调标记未完成，扩大后沿用同提交恢复和 blob 复用；已完整兼容缓存可直接返回既有元数据而不增加 blob 请求，不保证匿名/二级限流可用性。公开原生验收显式使用 30 并报告截断，不改变产品默认值。

- `POST /projects/{project_id}/repositories/{repository_id}/sync-github` 只接受已登记 `provider=github` 的仓库。
- `ref` 省略时读取默认分支，也可指定 branch、tag 或 commit SHA；每次有效同步保存 Commit/tree 元数据与逐文件 blob/status 快照。同一 ref 连续解析到相同 Commit，只有完整且引用兼容的快照可以直接返回，不再请求 tree/blob。截断/大小跳过、缺失或不兼容来源/任务引用时，下次显式同步重试并创建独立快照，保留已成功来源/历史；确定性空文件/编码/路径跳过仍可短路，见 ADR 0031。
- 使用 GitHub repository、commit、recursive tree 和 blob REST 端点。公开仓库无需令牌；私有仓库令牌只放后端 `GITHUB_TOKEN`，建议仅授予 Contents read。
- 单份跳过码包括 `SOURCE_EMPTY`、`SOURCE_ENCODING_INVALID`、`SOURCE_PATH_INVALID`、`SOURCE_TOO_LARGE` 和 `GITHUB_IMPORT_TOTAL_SIZE_EXCEEDED`。
- 后续 Commit 优先按“路径 + blob SHA + 来源类型”复用未变化文件；已知 blob 仅在用户/项目/仓库、来源类型及解析任务兼容时复用，不跨 Markdown/Java 类型。完整文件集合中旧路径消失且相同类型 blob 只出现在一个新路径时记录 `renamed`；完整 tree 中消失的旧路径记录 `deleted`。截断 tree/文件集合不推断重命名，截断快照不推断删除。重试仍受每次 50 文件/20 MiB 预算限制，不增加分页或自动解析失败重试。
- GitHub repository `id` 持久化为 provider ID；远端 owner/name 变化时在同一仓库记录上更新规范坐标。重命名/删除只记录同步事实，不破坏性删除历史来源、分块或正式证据。
- 资料列表/详情从来源最近一次非 `deleted` 的快照记录派生固定 Commit 的 `git_url`；正式图谱、搜索和问答证据在同一文件 URL 上追加 `#Lx-Ly`。本地来源返回 `null`，远端删除后回退到最后一次存在的快照，`project://` 应用内 URI 保持不变。链接不持久化，见 ADR 0020。
- `POST /projects/{project_id}/repositories/{repository_id}/import-github-work-items` 显式读取最近更新的最多 20 个 Issue/PR；可选导入每项最多 20 条 Issue 评论，并为每个入选 PR 各导入最多 20 条 Review 与行级 Review Comment，把确定性 Markdown 送入同一解析/证据链路。
- `include_review_threads=true` 且配置后端 `GITHUB_TOKEN` 时，通过 GraphQL 为每个 PR 补充最多 20 个 Review thread 与每个 thread 20 个评论标识，保存当前解决状态、解决者、位置和过期状态。无令牌时 REST 导入继续成功并返回 `token_required`，不得把未读取误报为空线程。
- Issue/PR 以 provider item ID + `updated_at` 标识不可变版本；PR Review 活动作为独立来源，以 provider PR ID + 渲染内容 SHA-256 标识版本，因此 Review 编辑或 thread 状态变化不依赖 PR `updated_at`。相同版本复用来源/任务，变化时新建来源。两者的 `git_url` 都打开规范会话，不追加伪造的行号片段；行号定位本地 Markdown 快照，见 ADR 0021、0023、0024。
- 行级 Review Comment 保留 `in_reply_to_id` 回复关系，GraphQL thread 保留有界评论成员关系；查询快照不提供权威解决事件时间。附件、reaction、Webhook、定时同步、完整分页、强制推送可达性分析和自动失效传播仍不实现。

- 已保存 GitHub 快照可通过 `POST .../snapshots/{snapshot_id}/commit-source` 显式转成 SHA/UTC 时间/逐行引用提交说明的 Markdown 来源；不访问 GitHub/模型，不导入 patch，不自动解析或提升正式 Commit。内容不含 ref/统计/可变 remote 坐标，普通仓库范围字节去重支持跨 ref/改名复用。快照可空 `commit_source_id` / `commit_task_id` 只在引用兼容时复用，否则重新导入去重；返回任务当前状态。Commit 资料及证据 URL 打开规范 `/commit/{sha}`，不追加 Markdown 的 `#L`。测试 `tests/test_commit_sources.py`，原生 PostgreSQL 复验并发去重，见 ADR 0033。

- 快照 `/snapshots/{snapshot_id}/files` 是只读分页（默认 20，1–100），只读文件元数据，稳定按 path/UUID 排序。保留删除/跳过事实，外连接校验来源/任务用户、项目、仓库、类型和关联；无效引用置空不泄露 UUID。文件 URL 固定所选 Commit；删除项仅可打开保留本地来源，不伪造删除后 URL。总记录数不表示完整仓库，分页不绕过同步预算。测试 `tests/test_snapshot_files.py`，见 ADR 0034。

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

- Java 分析 V1 为按需派生、只读、不持久化，不进入正式图谱；统一能力/限制见 `docs/JAVA_ANALYSIS_V1.zh-CN.md` 和 ADR 0029。
- 静态导入扩展见 ADR 0030：未限定调用可经显式/通配静态导入定位到同仓库其他 ready 来源中的可访问静态方法；成员名称保守优先、显式导入阻止通配回退、`this`/`super` 不回退导入。响应 `receiver="import static"` 为标记，保留原方法 ID/行号与歧义；成员查找截断时不猜测回退。聚焦验证加入 `tests/test_java_static_imports.py`。
- 静态工厂扩展见 ADR 0036/0037：方法局部 `var` 的完整 `Type.factory(...)` 或未限定名 `factory(...)` 初始化只在所选可访问仓库内静态候选对一个可解析返回限定名一致时推断；普通方法体绑定从声明分号后生效。未限定名优先当前/继承成员，再使用显式/通配静态导入；任何成员名称均阻止导入回退。私有静态工厂仅支持精确当前类型内未限定名调用。所选导入所有者缺失、成员查找截断、非静态/外部/数组/类型参数返回或返回类型冲突时保持未知；受支持局部/参数/当前字段遮蔽类型限定名也停止推断。不支持链式、强制转换、条件、实例、this/super 限定或重新赋值形式。聚焦回归加入 `tests/test_java_factory_receivers.py`，覆盖原符号/行号、作用域、歧义和 API 仓库/ready 边界。
- 头部工厂扩展见 ADR 0038：`_HeaderBinding` 保留尚未解析的 `var` 工厂表达式；到主体左花括号时按源码顺序与方法体声明交错处理，资源列表按声明顺序绑定，不能预加载后面的资源名。复用原静态工厂查找并保留 `type_is_resolved`，绑定仅在主体/嵌套块生效，catch/finally/相邻块恢复外层。头部调用边仍省略，未知初始化保留遮蔽；复杂/带注解/传统 for 多变量声明等既有排除头部不扩大。聚焦回归加入 `tests/test_java_header_factories.py`。
- 保留 200 符号、500 同文件调用、同仓库 100 份 ready 来源、相关原文 20 MiB、400 相关类型，以及各 500 条类型关系/相关方法/跨文件调用上限。未归属来源只与同项目未归属集合解析。
- 普通块/if/else/while/try/catch/finally、带花括号的增强/传统 for 与资源 try 共用词法绑定。头部调用省略，头部绑定仅在主体生效；未知 var/数组元素/多异常 catch 遮蔽，不回退伪造字段/类型目标。
- 继承方法候选定位到原声明，支持未限定/this/super；覆盖签名抑制、菱形去重，私有/构造器/接口静态方法不继承。单次查找最多 256 状态，环/触顶标记 truncated。
- 实参数量/可变参数用于筛选，同数量类型重载、重复来源版本仍 ambiguous；不确定表达式不缩窄。resolved 不等于完整编译/运行时目标。
- 接收者安全回归见 `tests/test_java_receiver_safety.py`：字段/参数/局部数组及 varargs 参数保存 `None` 未知绑定，名称仍遮蔽字段/类型，不能退回元素类型；覆盖变量名前/后、多维方括号，泛型实参内数组不误伤外层标量。工厂局部绑定的 `type_is_resolved` 标识已解析限定名，后续直接在类型索引查找，不能再次套用调用文件的导入规则；默认包与重复版本必须保留原目标身份。显式/构造器绑定仍按原上下文解析。
- 不承诺完整 AST/classpath/访问与类型检查、泛型替换、动态分派、通用工厂/链式推断、完整数据流。无花括号控制语句、switch/模式/lambda/匿名/局部类型及不支持的复杂声明不在 V1 支持范围，不能把派生关系直接提升为正式知识。

- 证据原文跳转使用项目范围 `/projects/{project_id}/sources/{source_id}/chunks/{chunk_id}` 精确读分块，联合校验未归档项目、来源和分块的用户/项目/来源关联；缺失/错配 404，不依赖任务，不按名字或摘录猜目标。返回原 `position`/内容/行号/UUID，供现有 20 条分页定位；无模型/写入/迁移。聚焦测试 `tests/test_chunk_lookup.py`，见 ADR 0035。

## 只读代码符号检索

- `/projects/{project_id}/code-symbols` 只读 ready Java 来源，按名称/路径字面匹配，可选仓库及 type/field/method。复用 `java_symbols` 与大纲相同的符号 ID/行号，不执行调用关系分析或写入正式图谱。
- 扫描最多 100 份来源/20 MiB 原文，每份最多 200 符号；默认返回 50、最多 100。扫描内匹配数不是全项目总数；任何省略都标记 truncated，不把有界空结果说成全项目无目标。
- 命中携带可空 chunk_id/0 起始 chunk_position、任务/仓库及固定 Commit/行号链接。前端按既有每页 20 分块跳转，ready 资料即使任务引用缺失仍可读取。
- 聚焦测试 `tests/test_code_search.py`；边界与双语验收见 ADR 0032。

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
python -m pytest tests/test_sources.py tests/test_parsing.py tests/test_source_list.py tests/test_worker.py tests/test_github_import.py tests/test_github_activity.py tests/test_java_structure.py tests/test_java_v1.py
```

重点覆盖：

- 扩展名、大小、编码、空文件、`source_type` 校验。
- 同一可空仓库中的相同字节重复上传复用；不同仓库、不同项目或不同内容新建。
- 分块数量、类型、标题路径、行号、哈希、ID 稳定性。
- 手动执行幂等、失败重试、运行中 409。
- Worker 租约接手、旧执行写入被拒、次数上限、`--once` 子进程退出码。
- GitHub 默认/指定 ref、完整同 Commit 短路、不完整同 Commit 恢复、类型安全的路径/blob 复用、来源/任务引用校验、保守重命名/删除、provider ID 仓库改名、快照历史、不可变文件/行号 URL、远端删除回退、tree/文件/字节截断、raw blob 流式大小限制和供应商错误脱敏；恢复回归使用 `tests/test_github_sync_recovery.py`。
- GitHub Issue/PR 类型筛选、工作项与 Review 快照版本复用、Review 内容/thread 状态变化建新来源、无令牌降级、各类评论/线程截断、规范会话 URL、单项大小跳过和供应商错误映射。
- Java 跨文件直接类型/字段/参数/直属局部变量接收者解析、声明顺序、遮蔽、重载歧义，构造器初始化 `var`、返回类型一致的类型限定静态工厂 `var`、未知初始化的遮蔽，以及通用工厂/链式/数组/匿名类、多变量声明、词法块生命周期、兄弟块隔离、增强 for 元素绑定/未知遮蔽/头部隔离、try/catch/finally 生命周期与资源作用域隔离和不支持块边界。
- 正式证据存在时重解析失败（如已实现相应测试）。

## 完成检查

- [ ] 上传边界与错误码未变松。
- [ ] 去重仍限定在用户 + 项目 + 可空仓库 + 来源类型 + SHA-256。
- [ ] 分块仍是原文精确切片，行号仍从 1 开始。
- [ ] 租约 fencing 没有被绕过。
- [ ] 文档（`API_CONTRACT.md`、后端 README、ADR 0003/0004）已同步。
- [ ] 实际运行的测试与结果已记录。

## Source discovery filters (ADR 0049)

Source listing accepts literal filename/relative-path q (max 200), registered source_type and source_status. Apply all conditions before count/pagination in the existing user/project/archive scope, and preserve parsing task links and GitHub provenance. Source status is not task status. Reads must not parse, extract or call providers. Focus tests/test_source_filters.py tests/test_sources.py; the native runner includes the filter suite.

## Projected source pagination (ADR 0053)

list_sources selects only list fields (omitted columns raiseload), keeps repository display and uses a scoped window rank to read one latest parsing task per visible source. Preserve existing supported task types, filters/count/page order and created_at/id descending ties; parsing/detail still read full content explicitly. SourceListItem must serialize without loading content or task error histories. Query-count/projection/latest-task regressions run in SQLite and native PostgreSQL (tests/test_read_performance.py).

## 2026-10-26 功能补全更新

GitHub continue_from_snapshot 固定提交/tree/ref，缓存 scan_state/frontier；每步 10 目录及 50 文件/20 MiB，旧快照不可变；仅完整序列判断删除。单目录截断/清单上限明确 blocked。前端本地文件夹最多 10,000 份顺序导入并复用相同内容。

## 2026-10-29 当前优化边界

ADR 0061: code analysis resolves snapshot membership/immutable paths or explicit local one-version-per-path before helpers/providers. Metadata precedes bounded body reads (2000 metadata, 99 related, total20MiB); unready snapshot members mean partial. Do not apply DISTINCT to full JSON-bearing snapshot rows in PostgreSQL; use membership subqueries. Normal structure parsing remains separate. Regressions include renamed paths, repeated versions, budgets and native PostgreSQL.

## Single-project multi-agent extension (ADR0064–0065)

Canonical deterministic parsing now lives in app/analysis/{languages.py,parsers/{markdown.py,java.py,tree_sitter.py},bindings.py,compilers/adapter.py}; services paths remain module aliases for compatibility. Compiler helpers stay under backend/scripts and use existing frontend dependencies. Worker still parses without models. Agents get frozen SourceFile snapshots through services/agent_workflows, immutable selection stays in services/code_context. Do not pass DB sessions into agent contexts or run imported source/build scripts.


## Derived symbol reuse and shared syntax records (ADR0071)

Code symbol search applies current scope/readiness/repository and100-source/20MiB scan limits before a process-local LRU. Keys include user/project/source UUID, actual content SHA256, language, SYMBOL_PARSER_VERSION and parser budgets. Cache only frozen symbol tuples and flags;128 entries/8MiB accounted metadata, no source body/tree/parser/URLs/access grants. Keep chunk/task/Git provenance live and bump parser revision for semantic changes. Dependencies restart processes. Shared frozen records live in analysis/structures.py, re-exported by old parser imports. Verify symbol_cache/code_search/java/multilanguage and native checks; never write derived syntax into the formal graph.
