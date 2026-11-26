# Knowledge Atlas 项目缺陷分析与优化建议（2026-11-26）

> 本文档基于对当前代码库（迁移 head `20261031_0023`）与已有评测报告的静态分析整理而成，面向毕业设计答辩、系统实用性与工程可维护性提供缺陷诊断、缺失功能清单与分优先级优化路线。本文档仅作规划与参考，不代表以下优化项已实施或已验证。

## 一、项目现状总览

项目已经构建了较为严谨的纵向核心闭环：

- **资料解析与证据溯源**：支持 Markdown 与 9 种代码语言（`java` 专用解析 + `tree-sitter` 多语言解析），保留精确行号与 `SourceChunk` 原文切片。
- **受控知识入图**：模型仅输出带逐字原文引用的候选（`CandidateKnowledge`），经人工审核后在同一 PostgreSQL 事务中写入正式节点、关系与证据，并提供 `SUPERSEDES`、有效区间 `[valid_from, valid_to)`、别名与合并身份管理。
- **可追溯检索与问答**：支持 `keyword`、`bm25`、`bm25_source`、`vector`、`hybrid`、`rrf` 六种检索模式及逐条结论引用校验（`evidence-claims-v3`）。
- **异步与 Agent 框架**：具备 `worker` 解析队列、`assistant_runner` 异步助手执行器、持久化检查点、操作审批及离线评测脚本。

在此基础上，从**毕业设计展示效果、核心检索性能、功能完整度与论文实验闭环**四个维度审视，仍存在若干关键短板。

---

## 二、当前主要缺陷

### 1. 真实图谱可视化退化为“4 列静态网格”（答辩展示最大短板）

- **现状定位**：[frontend/package.json](../frontend/package.json) 仅依赖 `vue` 与 `element-plus`，未接入任何图可视化库（如 AntV G6、Cytoscape.js、ECharts Graph 或 D3-force）。
- **代码表现**：[ProjectGraph.vue](../frontend/src/components/ProjectGraph.vue#L139-L148) 的 `layout` 与 `positioned` 计算属性直接将节点按固定 **4 列等距网格**排列（`columns = Math.min(4, Math.max(1, nodes.length))`），并绘制直线 SVG 连线。
- **影响**：
  - 节点数量增加后连线交叉严重，无法直观展示知识拓扑、中心枢纽、语义聚类或 `SUPERSEDES` 时序演化流向；
  - 不支持节点拖拽固定、按关系类型筛选边或视图重排；
  - 与演示组件 [KnowledgeGraph.vue](../frontend/src/components/KnowledgeGraph.vue) 的环形轨道图形成明显反差，不利于答辩现场演示真实项目数据。

### 2. 检索底层性能与 `hybrid` 融合算法缺陷

- **缺少 pgvector 向量索引且维度写死**：
  - 迁移 [20261018_0006_knowledge_embeddings.py](../backend/migrations/versions/20261018_0006_knowledge_embeddings.py#L14-L36) 仅创建了 `(user_id, project_id, model)` B-tree 索引，未对 `embedding`（`VECTOR(1024)`）创建 `HNSW` 或 `IVFFlat` 索引，向量检索实际执行全扫描。
  - `ck_embeddings_dimensions` 检查约束及 [embeddings.py](../backend/app/services/embeddings.py#L29-L30) 将向量维度固定为 `1024`，更换 768/1536/3072 维嵌入模型需修改表结构与迁移。
- **BM25 依赖应用层全量批扫描**：
  - [search.py](../backend/app/services/search.py#L183-L227) 的 `_bm25_search` 每次检索均按每批 200 个实体从 PostgreSQL 拉取最多 50,000 个实体及证据到 Python 端执行 [lexical.py](../backend/app/services/lexical.py#L20-L35) 分词（单字 + 相邻二字 bigram）与计分。
  - 根据 [性能测量报告](../evaluation/performance/2026-10-29-scale/README.zh-CN.md#L13-L18)，温缓存下 1,000 实体关键词检索 p95 为 `1452.5 ms`，10,000 实体 BM25 p95 为 `616.5 ms`。
- **`hybrid` 模式召回率异常偏低的实现原因**：
  - 在 [public-v2 验收报告](../evaluation/results/2026-10-26-public-v2-run1/REPORT.zh-CN.md#L8-L13) 中，`Hybrid` 的 Evidence Recall@5 仅为 **39.06%**（明显低于 `BM25` 的 73.44% 与 `Vector` 的 79.69%）。
  - 对照 [search.py](../backend/app/services/search.py#L52-L95) 与 [search.py](../backend/app/services/search.py#L334-L452)：`_hybrid_search` 的词法路调用的是 `_keyword_ranked`（而非 `rrf` 使用的 `_bm25_search`）。`_keyword_ranked` 按空格分词并对所有词项使用 `AND` 条件（`*term_conditions`），中文自然语言问题几乎必然 0 命中；同时 `0.4 * vector + 0.3 * graph` 的线性加权允许一跳高置信度邻居挤掉真正相关的语义命中节点。

### 3. 论文评测与人工验收闭环尚未完成

依据 [Holdout-v3 报告](../evaluation/results/2026-10-31-holdout-v3-clef-run1/REPORT.zh-CN.md#L4-L38)、[public-v2 报告](../evaluation/results/2026-10-26-public-v2-run1/REPORT.zh-CN.md#L15-L26) 与 [M5 状态报告](../docs/PROJECT_ASSISTANT_M5.zh-CN.md#L3-L79)：

- **人工盲评覆盖率为 0%**：回答质量完全依赖单个匿名裁判模型（`@cf/cloudflare/clef`），且大量裁判输出低于 `0.8` 置信阈值（`47/91` 正确性、`50/91` 完整性、`91/91` 拒答合理性、`80/183` 引用判断为不确定），缺少人工正确率及人机一致性指标。
- **自动知识抽取链路未量化评测**：检索/问答实验基于预先回放的夹具知识图谱，未统计端到端 LLM 抽取的实体/关系 Precision、Recall、F1 与常见错误类型。
- **Project Assistant M5 停留在离线预演**：20 项开发任务已完成冻结与零调用 preflight，但 `live_execution_allowed=false`，尚未产生真实执行与评分数据。

### 4. 长耗时同步调用阻塞与模型厂商方言耦合

- [deepseek.py](../backend/app/llm/providers/deepseek.py#L38-L218) 全部采用同步 `httpx.Client` 且设置 `"stream": False`，问答无流式输出体验；[embeddings.py](../backend/app/services/embeddings.py#L172-L217) 重建向量在单次 HTTP 请求内同步遍历所有批次，中途失败会丢弃已算向量。
- [config.py](../backend/app/core/config.py#L26) 与 [.env.example](../backend/.env.example#L16) 默认模型为 `deepseek-flash`，且请求体固定传入 `"thinking": {"type": "disabled"}` 与 `"response_format": {"type": "json_object"}`，切换到通用 OpenAI-compatible 服务或本地 Ollama 时存在兼容风险。

### 5. Neo4j 投影定位偏弱，双存储价值未充分体现

- [neo4j_graph.py](../backend/app/services/neo4j_graph.py#L90-L188) 仅支持按单一 `valid_at` 手动触发全量删边重建同步，不支持审核后增量同步或自动更新。
- 在 Neo4j 模式下前端隐藏了历史时间查询表单（[ProjectGraph.vue](../frontend/src/components/ProjectGraph.vue#L297)），且查询能力仍限于 1–2 跳邻域，未利用 Cypher 发挥多跳路径发现或图算法优势。

### 6. 前后端局部文件膨胀与工程规范不统一

- 前端存在多个大型单文件组件：[App.vue](../frontend/src/App.vue)（978 行）、[SourceWorkspace.vue](../frontend/src/components/SourceWorkspace.vue)（约 42.6 KB）、[ProjectGraph.vue](../frontend/src/components/ProjectGraph.vue)（475 行 / 约 37.1 KB）；引入 `element-plus` 后仍存在大量原生表单与手写样式混用。
- 后端 [java.py](../backend/app/analysis/parsers/java.py)（约 74 KB）、[github_import.py](../backend/app/services/github_import.py)（895 行）体量较大；[deepseek.py](../backend/app/llm/providers/deepseek.py) 存在 4 处高度相似的 HTTP 响应读取逻辑；[assistant_runner.py](../backend/app/assistant_runner.py#L14-L40) 硬编码 `DEVELOPMENT_USER_ID` 与 2 秒轮询等待，编码风格与 [worker.py](../backend/app/worker.py) 不一致。

---

## 三、缺失功能清单

| 类别 | 缺失能力 | 代码依据与现状 |
| --- | --- | --- |
| 权限与基础管理 | 用户认证/登录、项目编辑与删除、资料删除/归档、手工创建或入图后编辑实体关系 | [dependencies.py](../backend/app/api/dependencies.py#L13-L14) 固定返回 `DEVELOPMENT_USER_ID`；[projects.py](../backend/app/api/routes/projects.py) 仅提供创建与查询；知识只能由抽取候选审核生成 |
| 多源数据接入 | PDF/HTML/YAML/JSON/日志解析、本地 `.git` 历史直接扫描、超大文件分段抽取 | [languages.py](../backend/app/analysis/languages.py#L3-L11) 仅支持 Markdown 与 9 种代码；[knowledge.py](../backend/app/services/knowledge.py#L109-L110) 超过 100 分块或 60,000 字符直接报错 `EXTRACTION_INPUT_TOO_LARGE` |
| 智能治理闭环 | 基于语义向量的实体消歧推荐、AI 辅助发现跨文档冲突/替代建议草稿 | [evolution.py](../backend/app/services/evolution.py#L223-L238) 仅基于规则做规范化精确同名扫描，未接入向量相似度或自动生成演化候选 |
| 图分析与路径检索 | 任意两实体间最短路径/关联路径查找、图中心度/热点统计 | [graph.py](../backend/app/services/graph.py#L286-L331) 仅支持单点 1–2 跳邻域查询 |
| 导出与个人备份 | 导出图谱（JSON/GraphML/CSV）与双链 Markdown（兼容 Obsidian）、前端交互式备份下载 | 备份恢复目前仅提供后端脚本，前端无导出入口 |
| 交互体验与本地推理 | 问答 SSE 流式响应、本地 Ollama 统一模型适配 | [ARCHITECTURE.md](../docs/ARCHITECTURE.md#L264) 已列为待决策项，尚未实现 |

---

## 四、分优先级优化建议

### P0：答辩与论文硬指标优先项（高投入产出比）

1. **升级真实项目图谱交互画布**
   - **目标**：替换 [ProjectGraph.vue](../frontend/src/components/ProjectGraph.vue) 的 4 列网格布局。
   - **方案**：引入 **AntV G6** 或 **Cytoscape.js**（或 ECharts Graph），支持力导向布局（常规浏览）与有向分层布局（追踪 `SUPERSEDES` 演化链），支持节点拖拽、按实体/关系类型筛选高亮、聚焦子图、画布导出图片及两点关联路径展示。
   - **验收标准**：真实项目导入数十个节点后无严重连线重叠，可交互拖拽、筛选并定位证据原文。

2. **补齐论文实验与人工盲评闭环**
   - **人工盲评**：使用已有 [blind-review.html](../evaluation/results/2026-10-26-public-v2-run1/blind-review.html) 与 `scripts.review_public` 完成至少一组冻结数据集的人工标注，在论文中报告人工正确率、可解释性得分以及模型裁判与人工判断的一致性（如 Cohen's κ）。
   - **修复 `hybrid` 检索缺陷**：将 [search.py](../backend/app/services/search.py#L339) 中的词法召回从 `_keyword_ranked` 切换为 `_bm25_search`（或做可配置开关保留旧基线对照），重新验证检索 Recall@5 消融对比。
   - **补测端到端自动抽取与 M5 小样本**：选取一组独立技术文档对 LLM 抽取结果做人工核验，报告实体/关系 Precision、Recall、F1 及逐字引用校验拦截率；对 M5 冻结任务集执行一轮小范围真实样例跑通并归档结果。

### P1：核心检索性能与业务功能增强

3. **数据库向量索引与词法检索提速**
   - 新增 Alembic 迁移，为 `knowledge_embeddings.embedding` 增加 pgvector `HNSW` 索引（`vector_cosine_ops`），并将向量维度改造为按配置或模型表隔离可配（解耦 `ck_embeddings_dimensions = 1024` 硬编码）。
   - 为正式实体名称/摘要及证据表增加 PostgreSQL `tsvector` + GIN 或 `pg_trgm` 索引，将初筛下推到数据库，减少 `_bm25_search` Python 端全量扫表压力。
   - 将 [embeddings.py](../backend/app/services/embeddings.py#L187-L217) 向量重建改为按批次增量落库，支持断点续建。

4. **支持大文档分段抽取与基础管理 CRUD**
   - 对超过 100 分块或 `extraction_max_input_chars` 的长文档增加**按章节/滑动窗口分批抽取**并汇总去重，消除硬性大小截断。
   - 补全项目修改/归档、资料归档/删除接口及前端操作，新增受审核记录保护的**手工新建实体/关系**与**已确认实体摘要修订**能力。

5. **打通基于向量相似度的实体消歧推荐**
   - 在 [evolution.py](../backend/app/services/evolution.py#L188-L245) 的只读治理接口中，利用同项目同类型实体的 `knowledge_embeddings` 计算近邻对，识别名称不完全相同但语义高度相近的候选对（如中英文别名、缩写差异），给出“疑似重复待合并”建议，继续由人工在现有合并入口确认。

### P2：工程重构、扩展接入与体验打磨

6. **模型适配抽象与 SSE 流式输出**
   - 抽取 [deepseek.py](../backend/app/llm/providers/deepseek.py) 公共客户端，将供应商特性参数（如 `thinking` 字段）改为按配置条件发送，增加对本地 **Ollama**（OpenAI-compatible `/v1` 接口）的开箱即用支持，修正默认模型名称配置。
   - 为问答接口 `/conversations/{id}/turns` 或新建流式端点增加 SSE 进度推送（检索完成 -> 生成中 -> 证据校验完成）。

7. **完善轻量鉴权、多格式导入与知识导出**
   - 实现轻量登录鉴权（JWT/Session）以激活数据库模型中的 `user_id` 隔离，或提供本地单用户访问口令配置。
   - 扩展 PDF / HTML 解析器及本地 `.git` 仓库历史导入；增加图谱 JSON / GraphML 与双链 Markdown 导出按钮。

8. **前端组件拆分与 Neo4j 能力增强**
   - 逐步将 [App.vue](../frontend/src/App.vue) 与 [SourceWorkspace.vue](../frontend/src/components/SourceWorkspace.vue) 中的子视图状态下沉到独立 composable；统一 [assistant_runner.py](../backend/app/assistant_runner.py) 的参数规范（支持 `--user-id` 与可配置轮询周期）。
   - 若保留 Neo4j 双引擎定位，可在知识确认/演化提交后增加异步增量同步，并在 [neo4j_graph.py](../backend/app/services/neo4j_graph.py) 补充 Cypher 两点最短路径与多跳子图查询接口。
