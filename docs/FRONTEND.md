# Knowledge Atlas 前端开发说明

本文说明当前 Mock 前端的结构、交互和后端接入方式。前端已经可以独立运行，所有业务数据暂时来自 `src/mock/data.ts`。

## 技术栈

- Vue 3 Composition API
- TypeScript
- Vite
- Element Plus 图标与消息提示
- 原生 SVG 知识图谱
- CSS 响应式布局

当前图谱使用原生 SVG，是为了精确还原原型并控制节点形状、关系标签和时间状态。后续数据量超过约 200 个可见节点，或需要复杂布局、拖拽和聚类时，再评估迁移到 AntV G6。

## 启动与构建

```bash
cd frontend
npm install
npm run dev
```

```bash
npm run build
npm run preview
```

`npm run build` 会先执行 Vue TypeScript 检查，再生成生产资源。

## 目录结构

```text
frontend/
├─ src/
│  ├─ components/
│  │  ├─ AppHeader.vue        # 品牌区、全局搜索和同步状态
│  │  ├─ SideRail.vue         # 左侧主导航和筛选入口
│  │  ├─ KnowledgeGraph.vue   # SVG 图谱、节点、关系和缩放
│  │  ├─ InsightPanel.vue     # 节点详情、证据、关联和追问
│  │  └─ TimelineBar.vue      # 知识时间回放
│  ├─ mock/data.ts            # Mock 节点、关系、证据和时间点
│  ├─ App.vue                 # 页面状态与组件编排
│  ├─ types.ts                # 前端领域类型
│  ├─ styles.css              # 全局视觉和响应式规则
│  └─ main.ts                 # 应用入口
├─ index.html
└─ vite.config.ts
```

## 当前页面状态

`App.vue` 维护以下页面级状态：

| 状态 | 用途 |
| --- | --- |
| `selectedId` | 当前选中的知识节点 |
| `timelineIndex` | 当前查看的知识时间点 |
| `visibleTypes` | 当前显示的节点类型 |
| `panelOpen` | 详情侧栏或移动端抽屉是否打开 |
| `filterOpen` | 类型筛选面板是否打开 |

时间或类型变化后，如果当前选中节点不再可见，页面会自动切换到第一个可见节点，避免图谱和侧栏状态不一致。

## 图谱交互

- 节点支持鼠标点击、Enter 和 Space 键选择。
- 当前节点使用双层酒红色描边，直接关联节点保持较高对比度。
- 项目、概念、决策、问题和代码实体使用不同形状与颜色。
- 关系标签使用等宽字体；与当前节点相关的边会高亮。
- 支持放大、缩小和重置视图。
- 类型筛选和时间轴会同时影响节点与关系。

## Mock 数据结构

核心类型定义位于 `src/types.ts`。

```ts
interface KnowledgeNode {
  id: string
  label: string
  subtitle: string
  type: NodeType
  x: number
  y: number
  size: number
  description: string
  confidence: number
  validFrom: string
  project: string
  evidenceIds: string[]
}
```

当前 `x`、`y` 和 `size` 只服务于演示布局。接入后端时，领域接口不应要求后端生成画布坐标；前端应根据返回数据计算布局，或单独保存用户调整后的视图配置。

## 响应式策略

- 桌面端使用“图谱工作区 + 详情侧栏”双栏布局。
- 中等宽度下详情侧栏变为右侧覆盖层。
- 手机端详情变为全屏抽屉，主导航移动到底部。
- 图谱保持足够大的内部画布，通过裁切显示核心区域。
- 所有主要按钮具有可见键盘焦点，并支持减少动态效果偏好。

## 接入真实 API

推荐按以下顺序替换 Mock：

1. 创建 `src/api/http.ts`，统一处理基础地址、超时和错误。
2. 创建 `src/api/projects.ts`、`knowledge.ts`、`questions.ts`。
3. 将 `mock/data.ts` 保留为开发演示和前端测试夹具。
4. 在页面增加加载、空数据、失败和重试状态。
5. 图谱数据量增大后，增加分页、按中心节点展开和最大可见节点数。
6. 问答接口使用流式响应时，只展示公开处理阶段，不展示模型内部推理。

接口草案见 [API_CONTRACT.md](API_CONTRACT.md)。

## 视觉约定

| Token | 色值 | 用途 |
| --- | --- | --- |
| Ink | `#15292d` | 主文本、导航和主要按钮 |
| Teal | `#2a6570` | 技术概念、检索状态和交互强调 |
| Rose | `#a9345f` | 当前节点、技术决策和时间状态 |
| Amber | `#d8a62c` | 项目节点与辅助提示 |
| Paper | `#f8fbfb` | 内容面板背景 |
| Grid | `#c9d5d7` | 边框、网格和次要结构 |

视觉目标是接近技术制图纸和知识地图，而不是通用后台仪表盘。

## 已知限制

- 左侧项目、资料和问答记录入口目前仅显示阶段提示。
- 搜索只匹配本地 Mock 数据，没有拼音、别名和服务端检索。
- 图谱节点位置固定，尚不支持拖拽、自动布局和框选。
- 问答内容是延时生成的模拟结果，不代表真实模型能力。
- 当前没有组件单元测试和端到端测试脚本。
