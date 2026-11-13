# 项目助手 M3 / M4

[English](PROJECT_ASSISTANT_M34.md)

2026-10-31 在 `feat/project-agent` 实现。[ADR0078](adr/0078-immutable-note-revisions.zh-CN.md)定义笔记，[ADR0079](adr/0079-governed-assistant-actions.zh-CN.md)定义能力和审批。M5 和真实模型质量仍独立。

复用现有原生 PostgreSQL、`backend/.venv`、`frontend/node_modules`、API、解析 worker 和独立 `python -m app.assistant_runner`，不新增服务或依赖。源码/业务库版本为 `20261031_0023`，就绪检查拒绝旧库。已有 v1 同步200、v2 排队202保持契约与历史重放行为。

## 笔记与可编辑结果

协作工作区增加600ms自动保存、不可变历史、原始笔记搜索、固定修订附件及显式资料快照。标题最多120字符，Markdown 最多60000字符。搜索最多扫描100份当前笔记/200000字符并披露截断；任务最多附加20个修订/200000字符。原文读取保持20份/200000字节/500分块；派生导入可列出更多文件，但披露读取截断。

每次编辑绑定请求 UUID 和预期父修订。并发编辑返回409并保留本地草稿。未知结果先读取，或显式使用同 UUID 重发；刷新只 GET。草稿按项目/标签页缓存。干净缓存载入最新已审批内容，未完成草稿暂停待核对。历史引用打开并聚焦精确修订，列表刷新不会覆盖编辑器导航。

Agent 新笔记仍是原始草稿。保存报告时把原始报告和精确引用放入修订来源记录，人工修改后仍保留；引用不证明改写后的文字。显式创建资料快照绑定原笔记修订，解析和抽取使用该资料；只有人工确认写入正式知识。原始笔记引用不伪造正式证据 ID。

## 一个任务内的受审核动作

提交 `protocol=assistant-task-v3`，选择资料版本并附加固定笔记修订。默认没有写入授权，界面提供这些 `allowed_actions`：

| 能力 | 结果 |
| --- | --- |
| `create_note_draft` | 新可编辑草稿和任务来源 |
| `propose_note_revision` | 完整修改前后提案、预期修订，人工审批 |
| `request_source_parse` | 显式笔记快照或确定性资料解析 |
| `import_repository_snapshot` | 提交时绑定仓库 UUID 和40位小写提交 SHA |
| `propose_knowledge` | 严格原文证据校验后的待审候选 |
| `propose_knowledge_change` | 候选确认、合并、新→旧 SUPERSEDES 或退役提案，人工审批 |
| `create_report_draft` | 只使用本任务实际引用的类型化报告产物 |

项目概览、资料/状态/证据、代码、冲突、笔记读取也经范围网关。导入/快照来源只通过持久化回执进入范围。不提供 shell、任意文件、发布、用户代码执行或远程写入工具。历史知识时间排斥当前附件和写能力；冲突检查是当前时间的线索，不是正式结论。

runner 保存工具检查点后停在 `waiting_approval`。核对完整拟议输入、修改前记录、目标/证据版本及提案校验值后，确认或拒绝精确操作。对象变化时保存冲突且不应用；拒绝不修改底层候选。审批请求绑定请求/操作 UUID、提案 SHA 和决定，同 UUID 重放幂等。现有领域服务原子提交业务变更和回执，正式证据、时序和身份校验继续生效。

审批发起零模型请求。全部待审提案处理后，显式选择继续，保留任务预算/检查点，只提供一次实际结果，包含新确认的精确正式证据；原知识搜索时间保持固定。模型/写操作未知结果须明确确认且保留尝试计数。取消或租约失效阻止迟到写入，包括其他事务取消 runner 后才执行的写入。

v3 所有角色共享8次模型/16次工具、0次嵌入和230秒执行时间。协调者在总预算内最多8/16，专用角色各保持4/8；v2协调者仍4/8。可在同一任务完成固定提交导入→解析→抽取候选→提案→人工确认→正式引用报告，不自动付费重试。确定性验收路径含抽取共用6次模型尝试。

## 整仓助手任务

在「协作任务 → 项目助手」输入目标，勾选「同步并解析整个 GitHub 仓库」，选择已登记仓库与分支、标签或提交。留空使用默认分支。启动 `python -m app.assistant_runner` 后，任务在浏览器关闭后仍由后台执行。首次后台导入解析 ref，成功批次和固定提交一起提交到 PostgreSQL。重新打开页面会读取已保存的任务和进度。

整仓使用 `assistant-task-v3` 和 `whole_repository=true`，需要 `repository_id` 及 `allowed_actions` 中的 `import_repository_snapshot`。可选 `repository_ref` 或 `repository_commit`，两者只能填一个。导入和解析按批执行，不消耗模型或工具调用次数。失败后可从已保存的批次继续，GitHub 文件树明确达到上限时会显示失败。

`scope.repository_progress` 报告阶段、快照、提交、已处理文件、解析成功、失败和跳过数量。报告阶段按目标关键词匹配路径并优先选取 README，最多读取 20 份资料、200 KB 原文和 500 个分块。报告引用绑定固定提交、路径及实际读取的原文行，按选取资料说明覆盖范围。

## API 新增

路径均在 `/api/v1` 下，并隔离当前用户与项目：

| 方法 / 路径 | 输入 / 结果 |
| --- | --- |
| POST / GET `/projects/{project}/notes` | request_id/title/markdown 创建；query 分页搜索 |
| GET / PUT `.../notes/{note}` | 当前笔记；request_id/expected_revision_id/title/markdown 保存 |
| GET `.../notes/{note}/revisions` | 分页不可变修订历史 |
| GET `.../notes/revisions/{revision}` | 精确原修订 |
| POST `.../notes/revisions/{revision}/source` | 幂等资料/解析任务映射 |
| POST `.../assistant/tasks` | v3能力、note_revision_ids 和可选 repository_id/repository_commit；202 |
| POST `.../assistant/tasks/{task}/approvals` | request_id/operation_id/proposal_sha256/decision |
| POST `.../assistant/tasks/{task}/artifacts/{artifact}/note` | request_id；保留来源的可编辑笔记 |

任务读取增加 operations、unknown_operations、remaining、final_artifact_id；GET、事件、产物读取继续免费。报告使用 `assistant-report-v2`；笔记引用含 note_id/revision_id/哈希/行号/摘录，source_id=null。正式证据及 evidence-claims-v3 不变。原方案中的 thread 和通用 input API 仍为拟议功能。

## 验证与迁移

用户已选择 Agent 执行，复用依赖并使用本地替身。完整后端1058通过/13跳过，覆盖率95.43%，门槛90%。最终运行时/队列/笔记/迁移聚焦及原生检查额外覆盖人工暂停事件。完整检查后最后39通过/2跳过的聚焦检查验证专用角色完成回执和45000字符笔记提案；完整修改前后记录保存在人工 API，模型工具回执保持精简。即使原实体行不变，别名、合并成员、生命周期和相关边历史变化也会使旧提案失效。前端156项、语句覆盖71.60%/行覆盖76.20%，门槛不变；生产构建通过。原生隔离升降升及296项通过，含双消费者和独立事务取消。没有真实模型或 GitHub 网络调用。

1440×1000桌面 Chrome 验证自动保存、继续修改后的旧引用、报告转笔记、笔记审批、候选确认和正式引用、显式继续、只读刷新、项目隔离/空状态、真实 Tab 焦点、面板滚动和无水平裁切。审批和刷新未增加替身计数，真实请求为0。浏览器发现的两处编辑器导航/缓存竞态已修复并加入回归。临时 QA schema 和服务验收后清理。

业务0021→0023前，`output/backups/pre-m34-20261031-01/` 保存了校验通过的31表快照。恢复到新 `ka_restore_m34_20261031_01` 后结构/内容指纹一致并清理。迁移新增5表，30张旧业务表内容指纹一致，schema 就绪通过；脱敏迁移记录在备份旁的 `migration.json`。未降级业务库；降级会删除新增笔记/审批历史，是需要已验证备份的维护操作。

冻结实验、授权、供应商账本、历史分数和人工评分0%保持原状。替身正确性不能证明模型语义质量、真实 GitHub 验收或托管 CI 通过。未启动 M5 发布、真实评估及演示录制。
