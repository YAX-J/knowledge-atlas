---
name: ka-frontend-workspace
description: Knowledge Atlas 的 Vue 3 前端工作台。修改组件、项目/资料页、候选审核、项目图谱或交互状态时使用。触发词：frontend, Vue, component, workspace, graph UI, accessibility, 前端, 组件, 页面.
---

# Vue 前端工作台

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
| `SourceWorkspace.vue` | 项目/资料列表、Markdown/Java 桌面端单文件/文件夹选择（文件夹最多 50 份）、MD/JAVA 标记、解析、结构分块分页及 Java 符号/同文件调用/跨文件类型关系大纲 |
| `CandidateReview.vue` | 候选、证据、改名/摘要、确认/拒绝 |
| `ProjectGraph.vue` | 真实项目图谱、筛选、邻域、详情与证据 |
| `KnowledgeSearch.vue` | 项目关键词/语义/混合检索、显式索引更新、组成得分、关系解释、结果证据与清空/重试/选择意图 |
| `QuestionWorkspace.vue` | 真实同步问答、证据不足/错误状态、检索统计、引用原文与实体跳转意图 |

## 状态与请求

- 页面级状态集中在 `App.vue`；组件只收 props、发事件，不直接发请求。
- 用请求序号（`projectsRequest`、`sourcesRequest`、`detailRequest`、`chunksRequest`、`reviewsRequest`、`reviewAction`、`graphRequest`、`graphDetailRequest`、`searchRequest`、`questionRequest`）丢弃迟到响应。
- 切换项目/资料时先清空旧详情并递增对应序号；上传、执行、审核期间禁止切上下文。
- 文件夹上传由 `App.vue` 先用 `webkitRelativePath` 根段解析本地仓库 UUID，再顺序调用单文件 API，提交仓库 UUID 与剥离根段后的相对路径；逐份捕获错误，保留成功项，最终选择最后一份成功资料。列表与详情展示仓库名称，资料标题优先展示仓库内路径，正式证据标题使用“仓库名/仓库内路径”。
- 默认 HTTP 超时 30 秒；候选抽取和证据问答 240 秒；都不自动重试。
- 后端失败时展示错误和重试入口，不回退成演示数据。
- 分页参数：`page` 从 1 开始，`page_size` 1–100，默认 20。

## Mock 与真实数据边界

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

- 后端返回节点/边/`truncated`/`evidence_count`，**不返回坐标**；布局在前端。
- 当前布局是按节点数的网格（最多 4 列，画布最小 740×300），不是力导向。
- 支持类型筛选、一跳/二跳、中心节点、返回总览、刷新。
- 边提供加宽的透明命中区，选中用玫红；节点选中同样玫红。
- 详情侧栏展示名称、摘要、置信度、写入时间、证据（文件名、行号、标题路径、引用）和直接关系。
- 节点/关系很多时依赖 `truncated` 提示和列表兜底，不要一次渲染无限节点。

## 验证

- `npm run build` 必须通过。
- 浏览器桌面 + 手机宽度走查：加载、空、错误、重试、分页、长文本、键盘焦点、面板滚动。
- 涉及真实接口时启动后端；涉及抽取时说明用的是模拟响应还是真实模型。
- 当前没有组件单测和端到端脚本；不要声称有自动化 UI 测试。

## 不要做

- 不要为了一个页面引入路由或全局状态库；先把编排留在 `App.vue`。
- 不要让后端返回画布坐标。
- 不要在组件里直接 `fetch` 或复制请求逻辑。
- 不要用 `any` 绕过类型；集成边界确实需要时加注释。
- 不要把演示数据当作真实图谱能力写进文档。
