# Knowledge Atlas 实施计划

本轮优化：服务端候选筛选、治理类别筛选与双实体原文核对已实现；问答去重片段保留全部检索实体归属。本轮不含合并、撤销或供应商质量实验（ADR 0047）。

本轮优化：显式整批审核和零供应商索引状态已实现（ADR 0046）。名称预览后的选择继续使用逐项审核/提升规则；索引检查报告范围数量、内容新鲜度及扫描截断。撤销、合并与自动索引仍属后续。

2026-10-25 使用流程优化：新增可选 `rrf`（BM25＋向量排名融合），搜索默认仍为 keyword，问答默认仍为 hybrid；问答可选择 hybrid/rrf/vector/bm25，按原文位置去重并轮流分配证据预算。资料展示整份候选的实时审核统计；治理按摘要分组识别重复并提供原文核对入口；搜索/问答共享迟到响应隔离。见 [ADR 0045](docs/adr/0045-opt-in-rank-fusion.zh-CN.md)。这些是实现与回归改进，尚无新真实模型质量结论。

多语言解析 V1 已将原 Markdown/Java 导入链路扩展到 Python、JavaScript/JSX、TypeScript/TSX、Go、C、C++、C#，贯通单文件/文件夹、GitHub 文件、Worker、精确原文分块、大纲及符号检索。默认解析只做语法结构且不调用模型；新增显式有界 Agent 操作，可在兼容语言族的同仓库静态声明候选中分析跨文件调用。后端校验每个目标 ID 与精确源码行，结果保持临时派生且不进入正式图谱。见 [ADR 0040](docs/adr/0040-multilanguage-source-parsing.zh-CN.md) 与 [ADR 0041](docs/adr/0041-bounded-multilanguage-agent-call-analysis.zh-CN.md)。

[English](PLANS.md)

本文标明当前实施阶段，并指向详细路线，不替代 [开发路线](docs/ROADMAP.md)。

## 当前状态

已完成：

- 明确仓库用途和毕业设计范围。
- 实现可交互的 Vue Mock 前端。
- 验证桌面和手机端的知识图谱流程。
- 编写架构、知识模型、接口草案和开发路线。
- 初始化仓库协作规范和决策记录文件。
- 实现 FastAPI 应用、健康检查、错误结构和请求 ID。
- 实现项目、Markdown 来源和排队任务接口。
- 增加面向 PostgreSQL 的模型、Alembic 初始迁移和本地服务编排。
- 使用隔离的 SQLite 数据库实现后端接口测试。
- 增加带类型的前端 API 客户端基础，同时保持 Mock 为默认入口。
- 实现显式执行的 Markdown 解析、可按行定位的持久化分块和分块分页。
- 实现相同字节上传复用、确定性的分块 ID、幂等任务执行和失败重试。
- 前端接入真实项目创建/列表、资料列表/上传、解析/重试、原文预览和证据分块分页，同时保留 Mock 图谱。
- 实现可选的数据库解析 Worker、执行租约、旧结果覆盖保护、中断任务恢复和有次数上限的自动尝试。
- 实现显式 DeepSeek 抽取、证据校验、带审计的审核，以及确认候选写入受限的 PostgreSQL 实体、关系和证据。
- 实现只读项目图谱、实体详情和关系详情接口，按用户/项目/时间过滤并限制节点与边数量，并提供真实项目图谱前端页面。
- 实现正式实体名称、摘要和摘录的带证据关键词检索，支持排序、类型/时间过滤、有界结果及图谱/详情跳转。
- 实现显式构建的 1024 维正式实体语义索引、pgvector 余弦检索、内容哈希复用和前端关键词/向量模式切换。
- 实现固定权重的关键词/向量/一跳图关系可解释混合检索，限制候选规模、过滤不可见关系并返回组成得分。
- 实现同步证据问答：有界混合检索、严格 DeepSeek 输出、应用层引用 UUID 校验及真实前端工作台。
- 完成冻结的阶段六 V1 测评集：30 个合成来源与 40 个直接事实、跨文档、代码定位、时序和不可回答问题；每个可回答问题都包含精确到行的标准证据与标准答案，并提供确定性校验和覆盖检索、引用、人工答案评分、延迟及可解释性的预测评分器。
- 全部受支持代码语言均可显式运行有界 Agent 辅助跨文件调用分析。静态解析提供同仓库候选 ID 与精确源码行，模型只能对这些候选分类，输出保持非持久化派生代码结构；真实供应商质量和 C/C++ 构建上下文准确率仍待验收。
- 实现本地 UTF-8 Java 源文件上传及确定性的 `code`/`comment`/`type`/`method` 分块，保留精确源码行并复用现有解析 Worker 与证据链路。
- 实现桌面端独立的单文件与文件夹上传入口；文件夹最多提取 50 份支持的 Markdown/Java 文件，逐份上传、持久化相对路径，并保留部分成功结果与原有单文件去重语义。
- 在同仓库已解析来源间，按包与导入规则有界解析 Java `extends`/`implements`，在正式图谱之外展示目标路径和行号。
- 增加项目范围的本地文件夹仓库身份、仓库内相对路径、仓库感知的重复复用及仓库边界内 Java 类型解析。
- 增加项目范围的 GitHub HTTPS/SSH remote 规范化身份、可选的既有本地文件夹仓库关联、仅远程身份登记及仓库列表界面；登记过程不请求 GitHub，也不克隆仓库。
- 增加默认分支或指定 ref 的显式有界 GitHub 快照同步，通过既有仓库范围去重和解析任务链路导入最多 50 份 Markdown/Java blob，累计预算 20 MiB。
- 持久化 GitHub Commit/tree 与逐文件 blob 来源，支持完整同 Commit 短路、不完整快照重试、按来源类型复用 blob/任务、保守的重命名/删除记录，以及基于 provider ID 的仓库改名跟踪。
- 从持久化快照派生不可变 GitHub 来源/证据 URL，固定到 Commit 文件和精确行号；本地来源返回空值，远端删除后链接到最后一次存在的快照。
- 把最近更新的最多 20 个 GitHub Issue/Pull Request 及每项最多 20 条普通评论显式导入为确定性 Markdown；每个入选 PR 另生成包含最多 20 条 Review、20 条行级 Review Comment 与令牌支持的 20 个 Review thread 当前状态的独立内容摘要版本，并提供规范会话链接和桌面端入口。
- 增加仓库范围内显式类型的直接类型、当前类型字段、方法参数和方法体直属局部变量接收者 Java 方法调用目标，保守处理遮蔽，并在正式图谱之外展示目标路径、精确行号和歧义。

- 显式类型及构造器初始化 `var` 局部接收者支持普通块/if/else/while 花括号作用域，保留声明顺序、词法生命周期、兄弟块隔离和未知类型遮蔽，见 [ADR 0025](docs/adr/0025-constructor-initialized-java-var-receivers.zh-CN.md) 与 [ADR 0026](docs/adr/0026-scoped-java-local-receivers.zh-CN.md)。
- 普通方法体局部 `var` 由完整的类型限定静态工厂调用初始化时，如果可访问的仓库内候选对同一个返回限定名一致即可解析；不支持或歧义工厂仍保持未知。见 [ADR 0036](docs/adr/0036-bounded-java-static-factory-var-receivers.zh-CN.md)。
- 带花括号的增强 for 体支持显式类型元素接收者；未知 `var`/数组元素仅在循环体范围阻止回退，循环头部调用仍不生成提示，见 [ADR 0027](docs/adr/0027-enhanced-for-java-receivers.zh-CN.md)。
- 仓库内 Java 结构/调用分析 V1 已打包词法/头部作用域（含传统 for 与资源 try）、继承候选及保守参数数量筛选，见 [V1 验收范围](docs/JAVA_ANALYSIS_V1.zh-CN.md) 与 [ADR 0029](docs/adr/0029-java-analysis-v1.zh-CN.md)。这不代表阶段四全部 GitHub/语义工作完成。

## 当前阶段

2026-10-25 优化检查点：已实现有界零模型 BM25 及界面/运行器支持；空的匹配向量索引跳过查询嵌入，配置错误继续显式返回。同一冻结语料/图谱/索引的开发 Recall@5 为 74.49%，旧关键词为 0，供应商调用为零；6 道代码定位题仍未命中，4 道无答案题仍检索到文字。原默认与历史报告不改。见[复盘与后续优先级](docs/OPTIMIZATION_REVIEW.zh-CN.md)和[开发诊断](evaluation/results/2026-10-25-bm25/README.zh-CN.md)。进一步融合选型前先补独立数据/真实人工评分。

当前检查点（2026-10-24，取代下方此前暂缓状态）：用户授权按顺序完成补强清单 3—8，并允许限定范围 DeepSeek。第 3 项：30 份片段/50 道行级案例/10 种语言；第 4 项：可选只读工具 Agent，模型最多 4 轮；第 5 项：112 次真实请求、120 条盲评和两份抽取证据校验，真实人工评分仍待完成；第 6 项：5 组 PNG/SVG 图、输入哈希及向量与固定混合的有限组件对比；第 7 项：架构/API/状态与双语交付文档同步；第 8 项：前端组件测试、覆盖率、CI 定义、原生启动器及可选完整 Compose。原生检查/构建单独记录，Docker 构建及托管 CI 尚未在此运行。见[实验报告](evaluation/results/2026-10-24-models/REPORT.zh-CN.md)与[演示](docs/DEMO.zh-CN.md)。下一项需要真实评审填写分数，不继续未经授权的供应商调用。

以下为本轮授权前的历史检查点：

2026-10-24 按毕业设计收尾顺序完成第一项可复现项目初始化，及第二项三组真实嵌入纯检索基线。`scripts.prepare_evaluation` 重放语料标注，经普通解析/审核服务生成 30 来源、44 实体、10 关系、54 审核和一条历史替代链；`scripts.run_baselines` 固定实际知识/索引指纹，保存 120 条预测、逐题诊断与对比表。用户允许本轮真实嵌入，DeepSeek 继续暂缓。关键词中文完整问题零召回，混合组低于向量组，结果必须如实保留，不能声称混合方案普遍更优。下一项是跨文件调用的多语言金标准，其后再开发工具调用 Agent；完整进度见阶段六说明与 ADR 0042。

阶段六的测评集建设已经作为可复现的合成 V1 完成。语料与金标准位于 `evaluation/`，`python -m scripts.evaluate_dataset` 可校验逐字证据并为完整预测文件评分。受保护的运行器从严格匹配的30来源项目生成三组预测/指标，供应商调用显式授权，拒绝不完整索引、语料外证据和运行中数据变化。首轮真实嵌入纯检索结果位于 `evaluation/results/2026-10-24-v101/`；人工评分、实验图表和真实答案质量仍待完成。

用户于 2026-10-23 批准的完成范围：阶段四代码/GitHub 核心、阶段五时序/治理，再做整体验收。跨来源演化审核、历史图谱/搜索界面与只读治理已实现（ADR 0039，head `20261023_0015`）。已有 40 文件合成仓库集成和隔离原生 PostgreSQL 竞争/租约检查。真实公开 petclinic 已通过 30 文件截断预算验收；私有令牌及模型/嵌入质量仍暂缓，见[核心验收](docs/CORE_ACCEPTANCE.zh-CN.md)。以下段落记录阶段四实现基线，不表示要继续无限扩大 Java/编译器范围。

阶段四已支持带花括号的传统 for 与资源 try 头部工厂初始化 `var`，按源码/资源声明顺序处理，解析绑定仅在主体生效。头部调用继续省略，catch/finally/相邻块恢复外层绑定。见 [ADR 0038](docs/adr/0038-java-header-factory-receivers.zh-CN.md)。

阶段四已把工厂局部 `var` 推断扩展到未限定名的当前/继承静态成员及显式/通配静态导入，保留成员名称优先、词法遮蔽、一致返回类型与原方法证据。类型限定名被遮蔽或方法类型参数返回时停止错误推断。见 [ADR 0037](docs/adr/0037-unqualified-java-factory-receivers.zh-CN.md)。

图谱详情、知识搜索与问答引用现在可按作用域内 UUID 打开本地精确原文分块，自动翻到对应页并聚焦/高亮。缺失或不可访问目标明确失败，不新增模型调用、图谱写入或迁移。这补齐来源追溯导航，阶段四仍在进行，见 [ADR 0035](docs/adr/0035-exact-evidence-source-navigation.zh-CN.md)。

已保存快照新增逐文件来源分页、有效资料/任务跳转、固定所选 Commit 的文件外链，以及删除/跳过/截断提示。这是阶段四的只读扩展，不是 Git diff 或完整仓库清单；不新增迁移或供应商调用。见 [ADR 0034](docs/adr/0034-snapshot-file-provenance.zh-CN.md)。

已保存的 GitHub 同步快照新增桌面历史面板，并可显式把提交说明转成 Markdown 资料，复用普通解析/抽取/审核链路与规范 Commit 链接；不读取 patch、不引入正式 Commit 实体，也不自动认定说明中的结论成立。该切片引入迁移 `20261022_0014`，见 [ADR 0033](docs/adr/0033-saved-commit-evidence-sources.zh-CN.md)。该阶段四基线已集成。

资料工作台新增按名称/路径、仓库和类型筛选的有界 Java 符号检索，复用大纲 ID 并打开正确原文分块分页。这推进阶段四按文件/符号查询的验收项，不引入正式代码知识实体，见 [ADR 0032](docs/adr/0032-bounded-code-symbol-search.zh-CN.md)。

阶段四新增仓库内显式/通配静态导入方法调用，作为 Java V1 的有界扩展，保留原方法符号、成员名称优先、歧义与审核知识边界，见 [ADR 0030](docs/adr/0030-java-static-import-calls.zh-CN.md)。该阶段四基线已集成。

阶段四代码导入基线：本地文件有界切片可接收 Java 文件，使用 `code_parsing`，把精确源码行保存为结构分块，持久化本地文件夹仓库身份与仓库内相对路径，并复用现有 Worker 与证据流程。它能解析一小部分仓库内跨文件类型关系，以及显式类型的直接类型、字段、方法参数/局部变量、构造器初始化 `var` 和返回类型唯一的类型限定静态工厂 `var` 接收者调用，登记规范化的 GitHub 所有者/仓库坐标，显式导入有界的默认分支或指定 ref 快照，并把最近的 Issue/Pull Request 与 PR Review 活动版本导入为 Markdown。GitHub 文件同步已持久化 Commit/tree 与逐文件 blob 来源，复用未变化或已知 blob，保守记录重命名/删除，通过 provider ID 跟踪远端坐标变化，并从该历史派生不可变来源/证据链接；工作项按 provider ID 与 `updated_at` 保存版本，PR Review 活动按独立渲染内容摘要保存版本，因此 Review 编辑及令牌支持的 Review thread 当前状态变化不依赖 PR 时间戳。当前仍不代表已经具备完整 Java AST 或符号/调用图、通用工厂/链式推断、重赋值局部类型、实参类型重载选择或运行时动态分派、权威 Review thread 事件时间、Webhook、轮询、强制推送可达性分析或破坏性来源失效传播。见 [ADR 0012](docs/adr/0012-bounded-java-source-ingestion.zh-CN.md)、[ADR 0014](docs/adr/0014-bounded-cross-file-java-types.zh-CN.md)、[ADR 0015](docs/adr/0015-local-folder-repository-identity.zh-CN.md)、[ADR 0016](docs/adr/0016-normalized-github-remote-identity.zh-CN.md)、[ADR 0017](docs/adr/0017-bounded-cross-file-java-method-calls.zh-CN.md)、[ADR 0018](docs/adr/0018-bounded-github-snapshot-import.zh-CN.md)、[ADR 0019](docs/adr/0019-incremental-github-commit-snapshots.zh-CN.md)、[ADR 0020](docs/adr/0020-derived-immutable-github-evidence-links.zh-CN.md)、[ADR 0021](docs/adr/0021-versioned-github-work-items.zh-CN.md)、[ADR 0022](docs/adr/0022-bounded-java-declared-receiver-calls.zh-CN.md)、[ADR 0023](docs/adr/0023-versioned-github-pull-reviews.zh-CN.md)、[ADR 0024](docs/adr/0024-bounded-github-review-thread-state.zh-CN.md) 与 [ADR 0036](docs/adr/0036-bounded-java-static-factory-var-receivers.zh-CN.md)。

本次功能切片已实现：

- `.java` 上传校验和 `source_type=java`，并将来源类型纳入重复复用语义。
- 确定性的本地解析器，识别顶层类型和常规直接成员方法；屏蔽注释、字符串和文本块时仍保留精确分块原文。
- 为 `code`、`comment`、`type`、`method` 分块保存稳定的 1 起始包含式行号、哈希、结构路径和 UUID，并把类型注解归入类型。
- 手动执行与带租约数据库 Worker 均支持 `code_parsing`。
- 桌面资料工作台支持上传、MD/JAVA 标记及 Java 分块类型展示。
- 增加有界来源结构接口与桌面大纲，展示稳定的类型/字段/方法符号及未限定名/`this.` 同文件调用提示，并与正式图谱隔离。
- 桌面端提供单文件与文件夹上传；文件夹忽略不支持类型和空文件，最多导入 50 份 Markdown/Java 来源并保存规范化相对路径。单份失败会独立提示，不回滚已成功资料。
- 在最多 100 份同仓库已解析 Java 来源内，通过显式导入、同包和通配导入解析顶层类型 `extends`/`implements`，并在来源大纲展示歧义与截断状态；未归属仓库的旧来源只在同项目未归属集合内解析。
- 以项目、类型和文件夹根目录名幂等解析稳定的本地仓库 UUID；文件夹资料保存仓库内相对路径，在仓库内去重，且 Java 类型解析不会越过仓库边界。
- 将 GitHub HTTPS、SCP 风格 SSH 与 `ssh://` remote 规范化为项目范围的所有者/仓库身份及标准 URL；既可登记仅远程仓库，也可关联已有本地文件夹仓库，且不会请求 GitHub。
- 已登记 GitHub 仓库可显式同步默认分支或指定 ref；最多 50 份、累计 20 MiB 的支持 blob 进入同一不可变来源/任务流程，并报告部分跳过与截断。
- 成功的 GitHub 同步会保存 Commit/tree 快照与逐文件 blob/状态；连续相同 Commit 仅在快照完整、引用兼容时直接复用。不完整/大小受限快照可显式重试，保留成功资料/任务的类型安全复用和不可变历史，见 [ADR 0031](docs/adr/0031-recoverable-typed-github-snapshots.zh-CN.md)。完整文件集合保守记录重命名/删除；GitHub provider ID 在远端坐标改变时保持仓库身份。
- 显式活动导入最多读取最近更新的 20 个 GitHub Issue/Pull Request 和每项 20 条普通评论，并为每个入选 PR 各读取最多 20 条 Review、行级 Review Comment，以及有令牌时的 20 个 Review thread 当前状态；工作项按 `updated_at` 版本化，Review 快照按渲染内容摘要版本化，资料与证据视图都打开规范会话。
- 依据导入与包规则，把直接类型限定、当前类型字段、显式类型参数和方法体直属局部变量接收者调用解析到同仓库其他已解析来源中的方法，并按遮蔽、声明顺序和名称歧义规则返回有界目标信息。

仍需验收：

- 手动上传并解析代表性 Java 文件，覆盖注释、字符串、文本块、多个顶层类型、构造方法、普通方法，以及有界解析器按类型/代码文本保留的语法。
- 在本地配置 DeepSeek 密钥，用短篇公开 Markdown 验证真实模型响应。
- 用代表性资料评估证据与模型输出质量；模拟测试不代表真实抽取质量。
- 在本机 PostgreSQL 浏览器中验收真实项目图谱，覆盖空数据、截断、筛选和时间过滤状态。
- 原生 PostgreSQL 独立会话上传/审核竞争、租约恢复及旧 Worker fencing 已在临时 schema 通过，不代表生产故障演练。
- 用包含已确认关系的代表性原生 PostgreSQL 数据评估语义与混合排序；当前真实服务冒烟项目有 7 个已索引实体，但没有已确认关系。

项目关键词、语义向量、可解释一跳图关系混合检索和第一版证据问答均已实现。实体消歧、问答历史、多轮 Agent 和流式响应仍属于后续开发。边界见 [ADR 0011](docs/adr/0011-synchronous-evidence-grounded-questions.zh-CN.md)。

## 后续阶段

1. 代表性真实回答验收与检索/提示质量评估。
2. 将 Java 解析扩展到当前受支持词法块、构造器初始化与有界静态工厂（类型限定、成员或导入）之外，并评估超出当前有界 GraphQL 状态快照、由 Webhook 支持的权威 GitHub Review thread 事件。
3. 实验、可选模型辅助治理扩展及部署；人工审核时序演化与规则只读治理已实现。

Markdown 解析、受 Schema 约束的审核和确认候选入图已作为边界清晰的切片完成。

详细交付物、风险和十二周安排维护在 [开发路线](docs/ROADMAP.md)。

## 计划规则

- 一次只推进一个边界明确的阶段。
- 通过 ADR 确认会影响架构的选择。
- 验收标准保持可观测、可测试。
- 当前阶段变化时更新本文，不必在每个小任务后更新。
- 不得仅因文档或脚手架存在就将阶段标为完成。
