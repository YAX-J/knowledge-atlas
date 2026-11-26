# Knowledge Atlas 前端开发说明

资料库增加项目编辑/归档恢复、资料归档状态筛选和恢复。`ProjectManagement`、`SourceArchiveControl` 与 `api/library` 管理显式操作；App 共用写锁阻止切项目/导航及路由重放，刷新项目列表同步版本。`AnswerFeedbackPanel` 仅在会话已保存的逐结论答案内显示，按回答轮次隔离请求；刷新 GET，未知提交保留 UUID，不自动写知识。

2026-11-26：真实图谱改用确定性的关联布局，可切换沿箭头方向的有向分层；循环关系同层排列，断连分量紧凑排列。支持拖动固定节点、Alt＋方向键移动、重置位置、按关系类型筛选，以及当前已加载子图内忽略方向的最短关联路径高亮。路径不代表因果推理或全项目可达性。局部位置不持久化；刷新图谱或切布局重排，切项目/时点/数据源清除路径与关系筛选。所有布局和路径操作在前端执行，不调用模型或写正式知识。

实现位于 `src/graphLayout.ts` 和 `ProjectGraph.vue`，不新增依赖。图谱 API 的范围、截断及精确证据定位保持。布局采用固定迭代，没有持续动画计时器。视觉验收使用独立 SQLite API 的合成回放图谱，不代表原生 PostgreSQL 或真实模型质量。

Current 2026-10-31: M3–M4 implement immutable editable notes and capability-scoped project actions with exact human approval (ADR0078–0079). Source/business head is `20261031_0023`, upgraded after a31-table backup/verified isolated restore; all30 old business-table content fingerprints were preserved. See [M3/M4 implementation and validation](PROJECT_ASSISTANT_M34.zh-CN.md). M5 remains deferred; this work uses local substitutes with zero live providers and preserves frozen evaluations/ledgers and human0%.

M2 界面默认提交 assistant-task-v2，轮询 queued/running；展示有效剩余角色预算、取消及带未知结果确认的显式继续。useProjectAssistant 保存继续请求 UUID，刷新/恢复仅 GET，不自动重复控制 POST。v1/旧工作流兼容。后端1036通过/12跳过、原生274、前端143/构建和桌面键盘/继续/取消验收通过，见[当前 M2](PROJECT_ASSISTANT_M2.zh-CN.md)。

项目只读助手 M1 已加入 Agent 页顶部（已通过本地替身/桌面验证）：ProjectAssistantPanel 展示目标、跨页精确资料版本/代码快照、历史/报告/补问；useProjectAssistant 管理项目隔离、未知提交 UUID、sessionStorage 只读恢复和轮询；api/assistant 使用独立协议。默认不选资料；已保存范围与新草稿分开，正文文本插值，引用跳精确分块或来源。旧两条工作流保留，事件标题使用独立 useId。前端140项、覆盖率门槛/构建和桌面浏览器已通过，见[验证步骤](PROJECT_ASSISTANT_M1.zh-CN.md)。

协作列表请求 summary=true，使用 AgentRunSummary；选择记录后 GET 完整 AgentRun，不将摘要误当详情。AgentWorkflowForm 独立维护草稿及代码版本选择，AgentWorkspace 保留历史/详情/恢复编排；原有范围隔离和付费操作边界保持。见 [ADR0071](adr/0071-bounded-read-caches-and-summaries.zh-CN.md)。

[ADR 0069](adr/0069-answer-claim-evidence.zh-CN.md)：新增 AnswerClaims 供单轮/持久化会话和协作回答复用。每条显示“附有引用”或“证据不足”，引用按 evidence 序号展示，并发出精确 EvidenceLocator 复用 useEvidenceNavigation；不插入 HTML，不猜测缺失引用。旧记录显示平铺正文及旧格式提示，不将旧回答补成有据条目。回归 answerClaims.test.ts、agentRuns.test.ts。

Vue 3 Composition API、TypeScript、Vite、Element Plus 和原生 SVG。默认 `VITE_DATA_SOURCE=graph` 打开真实项目图谱。可用 `workbench`、`api` 或 `mock` 分别直达项目总览、资料库或独立演示。真实请求失败时展示错误，不回退 Mock。

项目助手可选择登记的 GitHub 仓库和分支，提交后台整仓任务。任务详情显示固定提交、导入与解析计数，浏览器刷新通过 GET 恢复任务。关闭原标签页后，可从任务历史打开报告并跳转至原文分块。

关系图支持 PostgreSQL 与 Neo4j 数据源切换。进入 Neo4j 后只读取已保存快照，点击「同步到 Neo4j」才生成当前快照。工具栏分别显示快照总量和画布当前数量。Neo4j 的节点及关系详情使用快照 `valid_at` 读取正式记录和证据。切换项目或离开关系图会回到 PostgreSQL，URL 恢复只读取数据。

PostgreSQL 关系图提供时间轴。滑块沿实际有效期边界移动，右端为当前知识。拖动时预览日期，松手后查询切片，也可用方向键切换。历史切片用虚线标出在该时点有效、随后失效或被替代的关系。关系详情与原文使用同一查询时点，刷新保留所选时点。手动时间输入可查询轴上未列出的日期。

桌面验收使用 `test` 项目的 7 节点、2 关系快照，数据库解析 Worker 的一跳和两跳分别显示 2 节点 / 1 关系与 3 节点 / 2 关系，关系证据可键盘打开并聚焦原文。另用隔离项目验证首次同步和停用知识后的快照刷新，手动同步后总量从 3 节点 / 2 关系更新为 2 节点 / 1 关系。

## 模块甲板

前端采用方案 C 的 72px 图标轨、54px 上下文条和冷灰色画布。图标轨最上方是图谱、检索、问答和会话；左上角标识返回图谱。图谱的项目下拉只列出已读取的项目和当前项目，可从命令面板打开「我的项目」管理和翻页。工作台以六块白色卡片呈现知识脉搏、四项读数、项目概览、待办、最近动态和知识复用。桌面端卡片在甲板内独立滚动，可拖动卡片标题重排、使用卡片控制按钮收起或放大，也可从上下文条重置布局。在卡片收起按钮上按 `Alt+←` 或 `Alt+→` 可调整顺序。

`Ctrl+K` 或 `Command+K` 打开命令面板，支持命令和当前项目知识范围。快捷检索仍使用来源位置增强的 BM25，在演示图谱中搜索已加载的示例节点。专注提问保留图谱、检索、问答和会话四个导航入口。从资料库可直达文件、来源仓库、代码结构和审核区域，从整理组可进入治理、消歧与停用。

读数来自项目概览接口。知识脉搏与最近动态基于当前已加载的资料列表，知识复用卡片提供现有的项目检索和会话入口。图谱默认铺满主区，筛选按需展开，选中节点或关系后展开详情。画布可缩放、适应视口，放大后拖动空白区域平移。时序回放在画布下方，状态栏显示可见规模、邻域、时点及标签状态。超过 50 个节点后可用节点列表访问名称。问答输入区固定在页面底部，检索统计显示后端返回的命中数和覆盖率。

## 协作页面

知识时点可由问题中的完整日期或「今天」「昨天」识别。回答显示实际时点和来源。「修改查询时点」将原问题带回输入框并聚焦日期字段。模糊时间会显示「手动选择时点」入口。

证据问答和会话可在提交时选择本地知识时点。按结论展开「查看支撑关系」可看到关系两端、类型、查询时点和有效期，再打开该关系的原文分块。界面使用回答中保存的快照，历史答复可重新打开。

主数据库切换对比留空单时点字段，在问题里写出实体和两个完整日期，或用「切换前后有什么变化？」查询唯一的已审核切换。答复显示两个对比时点、审核确认的切换时间，并提供切换前后各自的关系详情和原文入口。证据会话刷新后可恢复已保存的两侧引用。

在候选审核页，主数据库替代建议并列显示新旧关系、原文和切换时间。两端实体确认后，打开「审核此次替代」再点击「确认替代并入图」。批量审核会提示用户单独处理该候选。

候选审核卡片展示原文时间表述、修订时间和建议有效期。「修改后确认」可按浏览器本地时间编辑生效时间和失效时间，提交时发送带时区的时间。正式入图后可通过关系图的历史时间查询核对边界。

工作台的首个入口「打开项目笔记」打开「笔记与 Agent」。当前修订保存后或打开历史修订时，可点击「分析笔记并提取知识」。任务记录提供所用修订和候选审核入口。审核确认后可打开项目图谱并定位快照中的原文。

ADR 0068 为 `AgentWorkspace` 接通检索方式、浏览器本地知识时间、固定提交/本地相关版本与提交前范围预览；选中记录显示后端白名单 `scope`，不将历史记录自动填成新草稿。`useCodeContextSelection` 复用 `useLatestRequest` 读取既有代码上下文接口；项目/来源/开关变化同步失效，拒绝迟到响应和失效选择，失败只读重试。历史时间清除并禁用当前代码；当前文件版本固定，未覆盖的本地相关文件在执行时取最新已解析版本。提交上限为 99 个显式相关文件版本，清单截断另行提示。覆盖率包括新组合模块，回归见 `tests/agentScope.test.ts`。

“协作任务”由 `pages/AgentWorkspace.vue`、`useAgentRuns`、`api/agents` 和 `components/agent` 接入当前 App。显式执行两条流程、显示请求计数/实际代码范围/已保存事件，转到原文审核后刷新并恢复。`#/agents?project=UUID&source=UUID&run=UUID` 通过 GET 恢复；未知提交 UUID 保存在 sessionStorage，先读状态再显式重发，轮询不产生新模型请求。切项目/卸载使迟到响应失效。问答引用复用原文定位。后端现逐事件保存进度和校验后的步骤结果（ADR 0067），仍以顶层任务状态判定完成，不将部分结果当作整个流程完成。详细限制见[协作说明](MULTI_AGENT.zh-CN.md)。

## 页面与导航

工作台 → 资料/解析/候选审核 → 图谱 → 证据会话沿用同一项目。Ctrl+K 聚焦项目搜索，Enter 显式运行来源位置 BM25。图谱按“关系图 / 知识检索 / 身份整理 / 演化与治理 / 停用记录”显示，保留历史时间和当前知识上下文，减少长页面滚动。

`useWorkspaceRoute` 使用 hash URL，无服务端 rewrite 依赖：

```text
#/sources?project=UUID&source=UUID
#/graph?project=UUID&entity=UUID&at=ISO_TIME&section=evolution
#/conversations?project=UUID&conversation=UUID
```

刷新/前进/后退恢复位置。URL 只保存 ID、时间和任务区，不写问题、原文或密钥。恢复按服务作用域验证项目；失效链接显示错误和重试。显式导航使迟到恢复失效；审核、上传与其他写入期间阻止上下文切换。会话位置恢复只读历史，不自动提交或重试模型请求。

## 编排职责

| 模块 | 职责 |
| --- | --- |
| `App.vue` | 项目、主导航、模块连接、原文读取与源码分析上下文 |
| `useSourceImport` | 导入、同步、续扫、解析和部分成功反馈 |

「同步整个仓库」自动请求同一 GitHub 提交的下一批，显示已处理文件和待遍历目录。批次失败时保留续传入口，成功批次的文件可由后台 Worker 解析。
| `useCandidateReview` | 抽取、候选过滤、依赖快照、单项/批量人工审核 |
| `useProjectGraph` | 真实图谱、实体/关系详情、邻域与迟到响应隔离 |
| `useKnowledgeSearch` | 搜索、索引状态/持久化任务、未知更新结果检查 |
| `useEvidenceNavigation` | 项目范围原分块读取、按 position 定页、UUID 高亮/焦点、取消/重试 |
| `useRepositorySnapshots` | 提交列表/文件分页、失败页重试、显式提交说明导入与焦点返回 |
| `useKnowledgeEvolution` | 历史、演化建议/审核、治理分类、双实体原文比较 |
| `useKnowledgeManagement` / `useKnowledgeRetirement` | 具名二次确认、同输入重试 UUID、历史写锁、审计列表 |
| `useConversations` | 保存会话、轮次分页、有限上下文、超时未知结果先检查及显式重试 |
| `useWorkspaceRoute` | URL 编解码、作用域恢复、历史导航、写锁和恢复失效 |
| `useCodeContextSelection` | 协作代码版本只读加载、固定提交/本地覆盖、跨上下文失效和提交前校验 |

组件通过 props/emit 接收状态和表达意图；API 请求放在编排模块中。API 类型在 `api/knowledgeAtlas.ts`，领域类型在 `types.ts`，语言注册表在 `sourceLanguages.ts`，Mock 仅在 `mock/`。

## 来源和代码上下文

资料支持名称/路径、类型和解析状态筛选，保留已打开原文，失败分页使用请求页号重试。原文定位只使用精确 chunk UUID，不猜测相似内容。快照文件保留原路径/blob/状态，不伪装 Git diff。

显式 Agent/编译器按钮先读取 `/sources/{id}/analysis-contexts`。GitHub 优先显示包含该来源的最近完整提交；可切换保存的其他提交。本地重复路径可明确选择一个相关版本，主文件始终是当前选中的来源版本。快照和本地选择不能混用，分析结果展示实际 commit/policy 和截断；上下文读取失败时支持刷新，不能悄悄改选。结构解析仍只读且免费；付费 Agent 需显式点击。

## 状态与交互规则

- 切项目、来源、时间、导航或卸载时，使对应旧请求失效；离开再返回同一 UUID 也不能恢复旧结果。
- 加载、空、错误和重试都有可见反馈。未知写入结果先查询状态，不自动重发可能计费的操作。
- 历史视图只读；修改候选/治理必须具名核对并显式确认，不能因筛选或预览自动写入。
- 冷灰画布、白色圆角模块和靛色主操作。保持键盘、可见焦点、减少动画和面板内滚动。
- 原文/模型文本使用文本插值，不使用 `v-html`。

## 验证

```powershell
cd frontend
npm run test:coverage
npm run build
```

覆盖范围包含 App、客户端、业务 API、关键组件和上述组合模块；整体门槛为 statements 55%、branches 50%、functions 35%、lines 60%，会话组件 lines 80%、会话模块 lines 90% / branches 80%。数字只代表该配置范围，不代表整个产品质量。桌面浏览器额外覆盖刷新、前进后退、焦点、空/错误、裁剪和滚动；不要求手机走查。

本轮证据见[验收](OPTIMIZATION_20261029.zh-CN.md)；旧逐轮说明见[历史前端文档](archive/pre-optimization-20261029/docs/FRONTEND.md)。
