# 单项目内的受限多 Agent

[ADR 0069](adr/0069-answer-claim-evidence.zh-CN.md) 已实现结论逐条关联证据：`evidence-claims-v2` 将有据结论绑定当前范围内的引用，将证据不足条目分开标明，引用可直达原文。后端生成兼容平铺字段；历史记录保留旧格式，不推断对应关系或重调模型。结构校验不证明语义蕴含。冻结实验、84/61 调用账本和 schema head `20261029_0019` 不变；人工盲评仍待用户完成。

[English](MULTI_AGENT.md)

Knowledge Atlas 已在现有后端内加入三个注册 Agent 和两条显式 LangGraph 流程。继续共用 Vue 前端、FastAPI、数据库、Worker 和依赖环境。目录与完整契约见[英文对应文档](MULTI_AGENT.md)；架构决策见 [ADR 0064](adr/0064-scoped-agent-modules.zh-CN.md)、[ADR 0065](adr/0065-durable-reviewed-workflows.zh-CN.md)，本次检查见[验收记录](MULTI_AGENT_ACCEPTANCE.zh-CN.md)。

## 当前目录

```text
knowledge-atlas/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── base.py, registry.py, runtime.py
│   │   │   ├── loop.py, graph_runtime.py
│   │   │   ├── code_analysis/
│   │   │   ├── knowledge_extraction/
│   │   │   └── evidence_qa/
│   │   ├── workflows/              # 契约、状态、路由、两条协作流程
│   │   ├── tools/                  # 仓库、原文块、作用域内的证据工具
│   │   ├── llm/                    # prompts.py、usage.py、providers/deepseek.py
│   │   ├── analysis/               # 语法解析、绑定、编译器适配
│   │   ├── services/               # 应用事务、授权范围与输出校验
│   │   ├── api/routes/agents.py
│   │   └── models/agent_run.py
│   ├── scripts/                    # 原有编译器辅助程序与验收脚本
│   ├── migrations/versions/20261029_0019_agent_workflows.py
│   └── tests/test_multi_agent.py, test_agent_tools.py
├── frontend/src/
│   ├── pages/AgentWorkspace.vue
│   ├── components/agent/
│   ├── composables/useAgentRuns.ts
│   └── api/agents.ts
└── docs/
```

迁移过的解析器、模型供应商、用量统计、代码引擎和工具循环保留原 `services` 模块别名，旧接口与测试替换仍指向同一模块对象；兼容文件不再维护第二份实现。提示词正文和旧版本值原样移动。Java/TypeScript/Go 辅助程序保留在 `backend/scripts`，复用现有项目依赖。

## 三个 Agent 与两条流程

| Agent | 输入与工具 | 输出边界 |
| --- | --- | --- |
| `code_analysis` | 服务端固定的源码版本；单轮、只读仓库工具或显式原生静态分析 | 校验后的派生调用判断、实际上下文及截断信息；不写正式图谱 |
| `knowledge_extraction` | 已授权原文块元数据、`read_chunk`、可选的代码结果提示 | 结构化候选；原有抽取服务逐项验证精确原文证据 |
| `evidence_qa` | 已确认且符合项目/历史时间的证据、`search_knowledge`、`read_evidence` | 引用 ID 必须来自正式检索证据；初始无证据时不调用模型 |

`knowledge_pipeline`：可选代码分析 → 工具读取原文并抽取 → 保存候选 → `awaiting_review` → 原有人工审核 → 显式恢复 → `succeeded`。代码结果只作提示，不能替代原文引用。任务保存的候选必须仍属于同一资料和抽取任务，且全部确认或拒绝后才能恢复。恢复不调用模型、嵌入或自动索引；人工拒绝也是合法的完成决定。

`question_pipeline`：可选代码分析 → 有范围的证据检索/工具问答 → 引用校验 → `succeeded`。代码结果只帮助导航，回答结论仍须正式证据。历史问答拒绝混入当前代码提示。新流程默认离线 `bm25`；原有问答和会话默认策略保持兼容。流程回答保存在任务结果中；现有持久化会话保留独立入口。

这两条流程按依赖顺序执行，提供有界工具循环和角色协作。后续新增 Agent 时实现输入/上下文边界，在 registry 注册，提供受限工具，并在显式流程加入节点及范围/预算回归；继续复用同一供应商和应用。

## 运行和持久化契约

现有后端环境执行 `.\.venv\Scripts\python.exe -m pip install -e ".[dev,evaluation]"` 安装更新依赖；LangGraph 在 `backend/pyproject.toml` 固定版本。已有库先备份再 `alembic upgrade head`。当前 head 为 `20261029_0019`，新增 `agent_runs`；就绪检查要求该表及预期版本，不会自动迁移。

共享上下文带用户/项目/资料/快照/历史时间/任务标识。每个角色最多四轮模型、八次工具；一次协作默认上限八次模型尝试、十六次工具、四次嵌入尝试，可降低至零。失败的供应商尝试计入预算。还限制输入输出、原文范围、时间和 JSON 结构；不开放 shell 或写文件工具。事件仅保存固定词汇和数字元数据，不保存提示词、原始工具参数或思维链；业务结果按原有规则保存已授权证据。调用时明确关闭 LangGraph 外部追踪上传。

以下路径以 `/api/v1` 为前缀：

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| POST | `/projects/{project_id}/agent-runs` | 显式同步执行，请求必须带 `request_id` UUID |
| GET | `/projects/{project_id}/agent-runs?page=1&page_size=10` | 当前项目任务分页，page_size 为 1–50 |
| GET | `/projects/{project_id}/agent-runs/{run_id}` | 保存的状态/结果/事件/用量/审核计数，不调用模型 |
| POST | `/projects/{project_id}/agent-runs/{run_id}/resume` | 检查已有人工决定，免费完成流程 |

```json
{
  "request_id": "UUID",
  "kind": "knowledge_pipeline",
  "source_id": "UUID",
  "include_code_analysis": true,
  "code_strategy": "tools",
  "model_limit": 8,
  "tool_limit": 16,
  "embedding_limit": 4
}
```

问答使用 `kind=question_pipeline`、去除首尾空白后 1–200 字符的 `question`、可选含时区的 `valid_at`，以及 `bm25|bm25_source|rrf|hybrid|vector` 中的 `retrieval_mode`。代码上下文可选 `snapshot_id` 或最多 99 个不重复 `version_ids`，须有代码资料并开启 `include_code_analysis`。资料整理必须指定已解析资料，不接受问题或历史时间。额外字段和越界预算校验失败；越权返回 404；同一 UUID 不同输入返回 `WORKFLOW_REQUEST_CONFLICT`（409）；未完成审核返回 `WORKFLOW_REVIEW_PENDING`（409）。

调用模型前先提交任务记录。同 UUID、同输入读取原任务；不同输入冲突。执行 UUID 与租约防止过期执行覆盖结果。过期运行记录读为 `interrupted`，不会自动付费重跑。[ADR 0067](adr/0067-durable-agent-progress.zh-CN.md) 规定每个事件保存元数据和用量，模型/工具/嵌入调用预留在执行回调前提交；这些边界要求当前执行仍有归属，并更新租约。代码/回答通过校验后、抽取候选已提交后保存步骤检查点；后续失败保留先前结果。同步 POST 期间 GET 可读取已提交进度；不提供事件流或崩溃后的自动逐节点续跑。原有抽取幂等同样生效：同资料/策略已成功时复用候选。抽取状态 GET 展示两种策略中最近创建的任务；旧抽取 POST 仍用原策略。

进度保存拒绝存在待提交 ORM 写入的会话，不会顺带提交未完成候选。保存失败（`WORKFLOW_PROGRESS_UNAVAILABLE`）或归属失效（`WORKFLOW_INTERRUPTED`）会阻止后续执行回调。调用前的预留可能保守计入尚未发出的请求，用量不是账单凭证。仅已成功提交的检查点可在进程崩溃后保留；抽取提交和协作检查点仍是两个事务。顶层任务状态始终有效，部分结果内的步骤状态不能视为整个流程完成。中断任务可查询，GET/同 UUID 重发不会将其变为自动付费续跑。

## 协作列表批量读取

`GET /projects/{project_id}/agent-runs` 只校验一次有效用户/项目，统计总数并读取当前页，再用一次查询读取本页候选的 ID/来源/任务/审核状态投影，不加载候选 payload、名称或摘要。固定用户/项目范围内，按每条任务精确且去重的候选 ID、来源和抽取任务匹配计数，因此复用同批抽取、候选子集重叠或缺失时仍与详情读取一致。空页和无候选页面跳过候选查询。

列表与详情共用响应投影，保留部分结果、用量、已保存范围和只读租约过期判断。页查询刷新已有 ORM 对象，全页用同一当前时刻判断过期。排序仍为 created_at 降序、id 升序，默认第1页/每页10项、最大50项；响应字段、迁移 head `20261029_0019`、详情/恢复审核检查及付费重放规则保持。总数、分页、计数仍是独立语句，不承诺跨语句的原子快照。

`backend/tests/test_agent_list_performance.py` 用合成任务复现旧列表路径，对比完整响应并记录 SELECT 数量。含候选 ID 的1/10/50条任务页面由6/33/153次降为4次，空页/无候选页面为3次。这是查询次数结果，不是 HTTP 延迟或生产容量测量。回归覆盖同时间戳分页、精确子集、越权拒绝、旧 ORM 状态和租约边界；原生验收包含该文件。此项检查不调用供应商，也不改前端。

2026-10-30 验证：聚焦43项通过；KA_NATIVE_COMPILERS=1 完整后端783项通过/8项跳过，语句覆盖率95.58%；原生 PostgreSQL17.10/pgvector0.8.7 验收205项通过，迁移升/降/升通过。临时 schema 已删除，应用迁移标记未改变。SQLite 与原生 PostgreSQL 均断言相同查询数及完整响应一致性，不产生真实供应商调用。本轮仅改后端，未运行前端构建或浏览器验收。

## 页面使用

在“资料与审核”打开一份已解析资料，再进入“协作任务”，选择资料整理或问答；代码分析可选。页面显示资料、请求上限、费用提示、保存结果、实际代码上下文和执行事件。[ADR 0068](adr/0068-explicit-workflow-scope.zh-CN.md) 接通 BM25/来源位置 BM25/RRF/混合/向量及可选浏览器本地知识时间，提交时转为带时区的 UTC 时间；默认仍为 BM25。历史问答禁用并清除当前代码分析。开启代码分析后通过既有 analysis-contexts 只读接口选择固定提交或最多 99 个本地版本覆盖；当前文件保持已打开的不可变版本，未指定的本地相关文件取执行时最新已解析版本。版本读取中/失败/选择失效时阻止提交，可只读重试。新草稿的范围预览与所选任务的已保存范围分开。抽取后打开原文审核，核对并确认/拒绝具名候选，返回任务刷新后继续；问答引用可跳回原文。

启动/列表/详情/恢复响应新增白名单 `scope`：retrieval_mode、valid_at、include_code_analysis、code_strategy、snapshot_id、version_ids。不适用的问答/代码字段为空值或空列表，不返回原始请求、来源哈希或提示词；客户端类型兼容旧服务缺失/null scope。保存范围不自动恢复为新草稿，也不会在刷新时重放。切来源重置代码选择，切项目还清空问题/时间/检索草稿。元数据截断保持明确提示，后端仍在编译器/供应商调用前校验作用域、字节与来源预算。

`#/agents?project=UUID&source=UUID&run=UUID` 只用 GET 恢复。sessionStorage 保存未知提交的 UUID；结果未知先读状态，之后才能显式重发同一 UUID。切项目/卸载使迟到响应失效。运行中的记录每三秒 GET 轮询；刷新和轮询不提交新模型请求。

## 验收边界

完整与聚焦测试使用模型替身，原生编译器和 PostgreSQL 验收单独执行。浏览器工作区使用自有临时 schema 和替身协议。本次重构没有新增付费实验；公开实验累计仍为 84 次模型 /61 次嵌入尝试。真实人工盲评仍由用户稍后完成。私有 GitHub、Docker 和远端 CI 保留此前明确的待验收状态。
