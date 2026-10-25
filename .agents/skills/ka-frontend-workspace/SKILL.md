---
name: ka-frontend-workspace
description: Knowledge Atlas 的 Vue 3 前端工作台。修改组件、项目/资料页、候选审核、项目图谱或交互状态时使用。触发词：frontend, Vue, component, workspace, graph UI, accessibility, 前端, 组件, 页面.
---

# Vue 前端工作台

多语言 V1（ADR 0040/0041）：文件选择/标签共用 `sourceLanguages.ts`，支持 Markdown、Java、Python、JS/JSX、TS/TSX、Go、C/C++、C#。上传由后端推断类型，不再强填 markdown；全部代码读取原结构接口，展示 `language`、`has_syntax_errors` 和截断，函数/方法与字段/属性共用旧类型。默认大纲不显示虚构调用；源码结构区的显式 Agent 按钮由 `App.vue` 调用独立接口并维护 `agentCallRequest` fencing，展示候选证据、置信度、简短依据及加载/空/错误/重试/截断状态。切资料清空旧结果，组件不直发请求。旧 Java 确定性分析保持；仓库卡片 `rescan` checkbox 仍由 App 经 API 发送。

前端同时服务两种数据：Mock 演示图谱，以及接真实 API 的项目/资料/审核/图谱/证据问答页面。两者必须保持边界，不能互相冒充。

## 何时使用

- 修改 `frontend/src/components/` 或 `App.vue`。
- 调整项目、资料、分块、候选审核、项目图谱的交互。
- 修改视觉样式、响应式、无障碍。
- 排查“切换项目后旧数据还在”“请求回来覆盖新状态”。

## 命令

```bash
cd frontend
npm install
npm run dev        # 5173
npm run build      # vue-tsc + vite build，提交前必跑
npm run preview
```

## 技术栈与目录

- Vue 3 Composition API + `<script setup lang="ts">`，TypeScript 严格。
- Element Plus 只用于图标和消息提示。
- 原生 SVG 画图谱，暂不引入 G6。
- 领域类型放 `src/types.ts`；接口类型放 `src/api/knowledgeAtlas.ts`。
- Mock 数据只放 `src/mock/data.ts`。

组件职责：

| 组件 | 职责 |
| --- | --- |
| `App.vue` | 页面状态、请求编排、迟到响应丢弃、导航切换 |
| `AppHeader.vue` | 品牌、Mock 搜索、同步状态 |
| `SideRail.vue` | 主导航与筛选入口 |
| `KnowledgeGraph.vue` | Mock SVG 图谱、缩放、节点选择 |
| `InsightPanel.vue` | Mock 节点详情、证据、关联、追问 |
| `TimelineBar.vue` | Mock 时间回放 |
| `SourceWorkspace.vue` | 项目/仓库/资料列表、GitHub remote 登记、显式 ref 快照同步与 Issue/PR/Review/thread 状态版本导入、Markdown/Java 桌面端单文件/文件夹选择（文件夹最多 50 份）、MD/JAVA 标记、解析、结构分块分页及 Java 符号/同文件调用/跨文件类型与显式类型的直接类型、字段、参数、直属局部变量接收者方法关系大纲 |
| `CodeSymbolSearch.vue` | 来源工作台的 Java 名称/路径/仓库/类型检索，只发出检索/清空/重试/打开意图，展示扫描限制和原文定位 |
| `RepositorySnapshots.vue` | 仓库已保存同步历史分页、长说明滚动、加载/空/错误/重试与显式提交说明资料导入/打开意图 |
| `SnapshotFiles.vue` | 快照逐文件来源分页、状态/原路径/blob/跳过原因、所选 Commit 链接与有效原文跳转意图 |
| `CandidateReview.vue` | 候选、证据、改名/摘要、确认/拒绝 |
| `ProjectGraph.vue` | 真实项目图谱、筛选、邻域、详情与证据 |
| `KnowledgeSearch.vue` | 项目关键词/语义/混合检索、显式索引更新、组成得分、关系解释、结果证据与清空/重试/选择意图 |
| `QuestionWorkspace.vue` | 真实同步问答、证据不足/错误状态、检索统计、引用原文与实体跳转意图 |

## 状态与请求

BM25 词法模式无需语义索引或模型，使用 `KnowledgeSearchMode='bm25'` 和可空 lexical 元数据，展示扫描规模/截断、BM25 分数非置信度。仅 vector/hybrid 显示语义索引统计，空 BM25 不提示更新索引；提交函数直接拦截 loading/rebuilding。App 请求序号与清空/切项目迟到响应隔离不变。回归 `npm run test:coverage`。

- 图谱/知识搜索/问答的本地原文按钮发出 `EvidenceLocator`，由 `App.vue` 的 `evidenceNavigationRequest` 调用项目范围单分块查询，按 position 翻页，聚焦/高亮原 UUID。定位加载/失败提示支持取消/重试；`clearSourceSelection`、项目切换或离开资料页使旧响应失效。`refreshSource` 接收初始分块页，不扫描全部页面、不自动解析/抽取，不把失败回退为同名或近似内容。见 ADR 0035。

- 快照文件面板使用 `snapshotFilesRequest` 与失败页号保存重试目标；切仓库、历史页、项目或关闭时清空并使旧响应失效。文件每页 20 项、有界滚动，保持文本插值；打开面板/原文与关闭返回按钮均管理焦点。删除项可读保留来源，不显示删除后文件 URL；详情沿用普通来源定位，不伪装成 Git diff。见 ADR 0034。

- 已保存快照历史使用独立 `snapshotsRequest`、项目校验和每页 10 条；切项目/关闭面板使旧响应失效。提交说明导入由 `App.vue` 的 `commit` 上下文锁编排，成功后刷新资料和历史、打开当前来源/任务并聚焦原文，不自动解析/抽取。仓库卡片及历史读取不联网 GitHub；Commit URL 使用规范 remote/SHA，不追加伪造 Markdown 行号。可空映射只用于按钮文案，服务仍校验引用。见 ADR 0033。

- 页面级状态集中在 `App.vue`；组件只收 props、发事件，不直接发请求。
- 用请求序号（`projectsRequest`、`repositoriesRequest`、`sourcesRequest`、`detailRequest`、`chunksRequest`、`reviewsRequest`、`reviewAction`、`graphRequest`、`graphDetailRequest`、`searchRequest`、`questionRequest`）丢弃迟到响应。
- 切换项目/资料时先清空旧详情并递增对应序号；上传、执行、审核期间禁止切上下文。
- 文件夹上传由 `App.vue` 先用 `webkitRelativePath` 根段解析本地仓库 UUID，再顺序调用单文件 API，提交仓库 UUID 与剥离根段后的相对路径；逐份捕获错误，保留成功项，最终选择最后一份成功资料。列表与详情展示仓库名称，资料标题优先展示仓库内路径，正式证据标题使用“仓库名/仓库内路径”。
- GitHub remote 表单只登记规范身份，可选关联当前页尚未关联的本地仓库；仓库卡片上的同步操作才会联网读取默认分支或指定 ref，最多导入 50 份支持文件。独立的活动导入操作读取最多 20 个最近更新的 Issue/PR、每项 20 条普通评论，以及每个入选 PR 各 20 条 Review、行级 Review Comment 与有令牌时的 20 个 Review thread 当前状态。同步与活动分别使用 `sync` / `activity` 加载和错误状态及 120 秒前端超时；完成后分别展示工作项、Review 快照、thread/已解决数量、令牌缺失及截断摘要并刷新仓库坐标。仓库卡片展示已知 provider ID，API 客户端可读取持久化快照历史。资料详情的可空 `git_url` 对文件打开固定 Commit，对工作项与 Review 快照打开规范会话；图谱、搜索和问答的文件证据 `git_url` 还固定到行号，外链统一使用新窗口和 `noopener noreferrer`。仓库列表请求使用独立序号丢弃切换项目后的迟到响应。
- 默认 HTTP 超时 30 秒；候选抽取和证据问答 240 秒；都不自动重试。
- 后端失败时展示错误和重试入口，不回退成演示数据。
- 分页参数：`page` 从 1 开始，`page_size` 1–100，默认 20。

## Mock 与真实数据边界

- 代码符号搜索使用独立 `codeSearchRequest`/`codeOpenRequest`，结果来自 `/projects/{id}/code-symbols`，不是正式知识检索。修改条件、清空、项目或离开资料页时丢弃迟到响应。打开结果先载来源，再按 chunk_position / 默认每页 20 条加载正确分块页，聚焦并高亮 chunk_id；操作期间使用既有上下文锁。仓库筛选选项来自当前仓库列表页，默认项目范围包含全部仓库。保持长路径换行、结果面板滚动、空/错误/重试及截断提示。

- `VITE_DATA_SOURCE=mock`（默认）打开演示图谱；`api` 默认打开资料工作台。
- 两种模式下，演示图谱及节点追问仍是 Mock，页面已标注。
- 真实页面：项目、资料、分块、候选、审核、项目图谱、独立证据问答。
- 不要把 Mock 记录塞进真实页面，也不要在请求失败时伪造成功。
- 项目搜索使用独立关键词/语义/混合模式与类型筛选，页头仍只搜 Mock。混合模式展示三路组成得分和可见一跳关系解释。语义索引必须由用户显式更新，组件只发出重建意图。`App.vue` 用 `searchRequest` 丢弃切换项目、清空和新搜索后的迟到响应；组件不直接发请求。选择画布外结果时加载邻域，再聚焦正式详情。
- 问答只保留当前内存结果，不伪造历史。切换项目、清空和新提问必须使旧响应失效；引用实体跳转到真实项目图谱。无证据、供应商错误都由后端真实结果驱动。
- 搜索结果样式使用 `.keyword-results`；全局 `.search-results` 属于页头演示下拉，不能复用。

## 视觉与无障碍

Token：

| 名称 | 色值 | 用途 |
| --- | --- | --- |
| Ink | `#15292d` | 主文本、导航、主按钮 |
| Teal | `#2a6570` | 概念、检索状态、交互强调 |
| Rose | `#a9345f` | 选中、决策、时间状态 |
| Amber | `#d8a62c` | 项目节点与辅助提示 |
| Paper | `#f8fbfb` | 内容面板 |
| Grid | `#c9d5d7` | 边框、网格 |

要求：

- 保持“技术制图/知识地图”风格，不要做成通用后台仪表盘。
- 节点可用鼠标、Enter、Space 选择；焦点可见。
- 支持 `prefers-reduced-motion`。
- 桌面双栏；中等宽度侧栏覆盖；手机底部导航 + 全屏抽屉。
- 原文、名称、摘要一律文本插值，禁止 `v-html`。
- 长文件名、长知识名要能换行，不撑破布局。

## 项目图谱

阶段五：`KnowledgeEvolution.vue` 展示历史替代链、人工建议/二次确认/审核快照和只读治理，仅发意图。历史时间同步传入图谱、实体/关系详情与知识搜索；清除时间清空旧搜索。`App.vue` 的 historyRequest/changesRequest/governanceRequest 独立 fencing，切项目/离开图谱使旧请求失效；写入期间禁止项目/主导航切换，历史视图禁用修改。确认替代后选择新知识并刷新当前图谱/审核，清除过时治理。审核队列使用有名称的 region、独立滚动与可见焦点；见 ADR 0039。

- 后端返回节点/边/`truncated`/`evidence_count`，**不返回坐标**；布局在前端。
- 当前布局是按节点数的网格（最多 4 列，画布最小 740×300），不是力导向。
- 支持类型筛选、一跳/二跳、中心节点、返回总览、刷新。
- 边提供加宽的透明命中区，选中用玫红；节点选中同样玫红。
- 详情侧栏展示名称、摘要、置信度、写入时间、证据（文件名、行号、标题路径、引用）和直接关系。
- 节点/关系很多时依赖 `truncated` 提示和列表兜底，不要一次渲染无限节点。

## 验证

- `npm run build` 必须通过。
- 浏览器仅桌面宽度走查：加载、空、错误、重试、分页、长文本、键盘焦点、面板滚动；按仓库 AGENTS.md，不要求手机验收。
- 涉及真实接口时启动后端；涉及抽取时说明用的是模拟响应还是真实模型。
- 现有 Vitest/jsdom + Vue Test Utils 组件/API 单测，运行 `npm run test:coverage`；覆盖范围见 vitest.config.ts，不冒称全站端到端回归。

## 不要做

- 不要为了一个页面引入路由或全局状态库；先把编排留在 `App.vue`。
- 不要让后端返回画布坐标。
- 不要在组件里直接 `fetch` 或复制请求逻辑。
- 不要用 `any` 绕过类型；集成边界确实需要时加注释。
- 不要把演示数据当作真实图谱能力写进文档。

## 2026-10-25 request and workflow updates

Search/question requests now share `composables/useLatestRequest.ts`; App retains orchestration and context checks. Preserve clear/project/time/unmount invalidation and retry mode. Question stop-wait discards the browser result, without claiming server cancellation. Selectable hybrid/rrf/vector/bm25 question retrieval preserves hybrid default; BM25 still needs a model to generate supported answers. Show whole-source backend `review_counts`, not current-page progress. Governance entity context must work outside the visible canvas and open real entity evidence. App-level regressions live in `tests/appRequests.test.ts`, with request races and component workflow tests alongside.
