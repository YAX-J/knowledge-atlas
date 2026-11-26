# Knowledge Atlas 当前路线与验收边界

2026-11-26 路径保留与真实图谱交互已完成本地离线验收。人工评测按用户要求暂缓，详见[按序优化进度](OPTIMIZATION_PROGRESS_20261126.zh-CN.md)。较早日期状态为历史。

M5 离线准备（2026-10-31）：已实现冻结的独立20项开发任务、18项验收矩阵、零调用预演、任务/评分导入及统一工程验收命令。M5 整体仍待授权后的真实执行器/夹具重放、真实质量、托管 CI、演示和发布。真实调用为零，无业务迁移，库版本保持0023；历史评估/授权/账本不变。见 [M5 状态与操作说明](PROJECT_ASSISTANT_M5.zh-CN.md)。

Current 2026-10-31: M3–M4 implement immutable editable notes and capability-scoped project actions with exact human approval (ADR0078–0079). Source/business head is `20261031_0023`, upgraded after a31-table backup/verified isolated restore; all30 old business-table content fingerprints were preserved. See [M3/M4 implementation and validation](PROJECT_ASSISTANT_M34.zh-CN.md). M5 remains deferred; this work uses local substitutes with zero live providers and preserves frozen evaluations/ledgers and human0%.

2026-10-31：第1–2项已完成：`evidence-claims-v3` 后端计算总体状态，使用[独立合成开发用例](../evaluation/development/claim-support-v3/README.zh-CN.md)验证正常/非法输出及 v2/平铺历史兼容。没有真实调用或 v3 质量结论。[历史裁判](../evaluation/results/2026-10-31-holdout-v3-clef-run1/REPORT.zh-CN.md)及其5条 v2 失败、冻结数据/账本原样保留，人工0%。后续版本冻结与论文定稿尚未执行。

当前离线模型评审支持 OpenRouter Jev、直连 TypeSafe Jev 和 CF 原生适配，人工评分覆盖率0%，真实 OpenRouter 评审尚未运行。见 [OpenRouter指南](OPENROUTER_EVALUATION.zh-CN.md) 与 [ADR0073](adr/0073-openrouter-jev-evaluation.zh-CN.md)。此前读取优化保留 ADR0071 记录。

[ADR 0075](adr/0075-server-derived-answer-support.zh-CN.md) 已实现 `evidence-claims-v3`：模型只返回 confidence、claims、missing_information，后端按所有条目状态计算 API 的 supported；逐条引用、缺失信息、预算与项目边界保持严格。v2 和平铺历史按原保存值读取/重放，不重算或调模型；v2 不作为新输出回退。使用独立虚构开发用例验证结构与兼容性，未测量 v3 真实质量。冻结 v2 实验/账本/评分和 schema head `20261029_0019` 不变，人工覆盖率0%。

当前实现及本轮验证见[验收报告](OPTIMIZATION_20261029.zh-CN.md)，任务进度见[计划](../PLANS.zh-CN.md)。按用户要求继续优化，评估采用 Jev 匿名自动评审。早期阶段说明与检查点见[历史路线图](archive/pre-optimization-20261029/docs/ROADMAP.md)。

## 全项目 Agent 改造（M1–M2 已通过本地替身验收）

M1–M2 已通过本地替身/原生/桌面验收，包含统一只读目标、类型化报告、异步队列/独立 runner、尝试/步骤/产物、取消和显式继续，见[当前 M2](PROJECT_ASSISTANT_M2.zh-CN.md)及 [ADR0077](adr/0077-durable-assistant-execution.zh-CN.md)。业务/源码 head20261031_0021，备份/恢复及旧表指纹已核验。v1/旧 AgentRun 兼容，冻结实验不变。M3–M5 的笔记/写入/质量发布验收未启动。

## 多 Agent 扩展

协作范围选择已接通（[ADR 0068](adr/0068-explicit-workflow-scope.zh-CN.md)）：检索方式、历史知识时间、固定提交或本地版本、提交前预览及刷新后只读核对。历史时间不混入当前代码，版本加载失败不静默执行默认分析；未指定的本地相关文件仍按执行时最新版本选择。

三个角色、两条有界协作流程及“协作任务”页面已实现，当前数据库 head `20261029_0019`。见[实现说明](MULTI_AGENT.zh-CN.md)。任务逐事件保存调用预留和过程状态，按步骤保存校验结果，后续失败保留已有结果；候选需人工审核后继续（[ADR 0067](adr/0067-durable-agent-progress.zh-CN.md)）。当前仍同步执行，不提供崩溃后的自动逐节点续跑或任意自主规划。

## 已交付的工作链

1. 多语言/Markdown/文件夹/GitHub 固定提交资料进入原生 PostgreSQL，Worker 有界解析，保存原文、行号与来源。
2. 模型只提候选，人工核对并显式审核；确认实体、关系、证据和审计事务提交。
3. 图谱、关键词/BM25/向量/融合检索回溯原文；别名、合并、历史有效期和演化经过人工确认。
4. 问答校验引用、无证据拒答，保存会话和有限多轮上下文；未知请求结果先检查，付费重试需明确操作。
5. 显式只读代码分析可选择固定提交或本地版本，避免同路径混入多个版本；编译器并不提供完整构建语义。
6. URL 恢复项目/资料/知识/历史时间/会话；关系、检索、身份、演化、停用各有任务入口。
7. 从已审核笔记关系对比数据库切换前后，在 PostgreSQL 关系图沿时间轴回看历史切片并打开原文。

## 本轮完成标准

| 优先级 | 可检查的交付物 |
| --- | --- |
| P0 | 应用库备份/恢复指纹、0018 版本和关键结构就绪检查、隔离原生完整业务流程 |
| P1 快照 | 固定提交路径和源码版本；重复同步/重命名/本地重复路径回归，越权拒绝 |
| P1 身份 | 规范化后长度校验、别名冲突、A→B→C 与解除检索回归 |
| P1 前端 | 会话超时/刷新/重试、依赖审核、历史只读、具名治理确认、跨项目/卸载失效 |
| P1 实验 | 7 份真实公开文档/24 道新题、版本指纹、开发/测试分离，人工评分明确待用户 |
| P2 性能 | 1000/10000 合成审核实体，20 次温缓存样本，SQL、p95、Python 峰值、请求估算和输出一致性 |
| P2 维护 | 三个编排模块、当前说明清理、历史归档、双语 ADR 与验收报告 |

## 下一步的实际依赖

模型自动评审不能补齐人工评价。本轮问答/裁判执行、离线汇总、图表及论文讨论/演示草稿已完成；原始结果和5条格式失败保留。后续改进优先在独立开发夹具复现历史版本、跨文档与引用支持问题，再使用新的独立测试评价；不从当前holdout调参，真实私人资料和部署仍待对应材料/权限。

BM25 v2 已将千条窗口替换为每批 200 个实体的按键分页，在最多 50,000 个可见实体上统一打分，每实体独立限制排序证据和文本。匹配总数、Top K 截断和扫描/文本省略分别返回，见 [ADR 0066](adr/0066-batched-global-lexical-retrieval.zh-CN.md)。旧规模报告仍代表旧协议，不证明当前全量召回或容量；同步批次尚不能跨请求恢复。后续先测量 v2 和代表性向量负载，再决定全文索引、ANN 或缓存。
