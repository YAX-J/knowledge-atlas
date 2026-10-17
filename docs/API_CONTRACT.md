# Knowledge Atlas 前后端接口草案

本文定义第一版前后端协作所需的最小接口。项目、Markdown 来源、任务和健康检查接口已经实现；其余接口仍是设计草案。字段调整时应保持错误结构和分页结构一致。

## 实现状态

| 接口 | 状态 |
| --- | --- |
| `GET /api/v1/health/live` | 已实现 |
| `GET /api/v1/health/ready` | 已实现 |
| `GET/POST /api/v1/projects` | 已实现 |
| `GET /api/v1/projects/{project_id}` | 已实现 |
| `POST /api/v1/projects/{project_id}/sources` | 已实现，仅 Markdown |
| `GET /api/v1/sources/{source_id}` | 已实现 |
| `GET /api/v1/tasks/{task_id}` | 已实现 |
| 图谱、搜索、问答和人工确认接口 | 规划中 |

## 基本约定

- 基础路径：`/api/v1`
- 数据格式：`application/json`
- 文件上传：`multipart/form-data`
- 时间格式：带时区的 ISO 8601，例如 `2026-10-17T14:30:00+08:00`
- ID：UUID 字符串
- 分页参数：`page` 从 1 开始，`page_size` 默认 20
- 前端不得依赖数据库内部节点 ID

统一错误结构：

```json
{
  "error": {
    "code": "SOURCE_PARSE_FAILED",
    "message": "资料解析失败",
    "details": {
      "source_id": "..."
    },
    "request_id": "..."
  }
}
```

## 项目

### 查询项目

`GET /api/v1/projects?page=1&page_size=20`

返回 `items`、`page`、`page_size` 和 `total`。

### 创建项目

`POST /api/v1/projects`

```json
{
  "name": "订单状态机",
  "description": "订单生命周期和事件一致性实验项目"
}
```

### 查询项目详情

`GET /api/v1/projects/{project_id}`

## 资料与任务

### 上传资料

`POST /api/v1/projects/{project_id}/sources`

表单字段：

- `file`：当前只接受 UTF-8 Markdown 文件，默认最大 10 MiB。
- `source_type`：可选，未填写时由后端识别。

响应：

```json
{
  "source_id": "...",
  "task_id": "...",
  "status": "queued"
}
```

### 查询任务状态

`GET /api/v1/tasks/{task_id}`

```json
{
  "id": "...",
  "type": "knowledge_extraction",
  "status": "running",
  "stage": "entity_resolution",
  "progress": 72,
  "error": null
}
```

任务状态建议使用：`queued`、`running`、`succeeded`、`failed`、`cancelled`。

### 查询资料原文

`GET /api/v1/sources/{source_id}`

返回资料元数据、SHA-256、解析状态、行数和最多 4000 字符的可预览内容，不返回服务器文件路径。

## 知识图谱

### 查询局部图谱

`GET /api/v1/projects/{project_id}/graph`

查询参数：

- `center_id`：中心节点，可选。
- `depth`：关系深度，第一版只允许 1 或 2。
- `types`：逗号分隔的节点类型。
- `valid_at`：查询指定时间点的有效知识。
- `limit`：最大节点数，默认 100。

```json
{
  "nodes": [
    {
      "id": "...",
      "type": "Concept",
      "name": "事件驱动架构",
      "summary": "围绕事件组织系统组件的架构方式",
      "confidence": 0.96,
      "status": "active",
      "valid_from": "2024-05-01T00:00:00+08:00",
      "valid_to": null,
      "project_id": "...",
      "evidence_count": 3
    }
  ],
  "edges": [
    {
      "id": "...",
      "type": "IMPLEMENTS",
      "source_id": "...",
      "target_id": "...",
      "confidence": 0.91,
      "status": "active"
    }
  ],
  "truncated": false
}
```

节点坐标不属于领域接口。前端自行计算布局；如需保存个人布局，使用独立视图配置接口。

### 查询节点详情

`GET /api/v1/knowledge/entities/{entity_id}`

返回实体、直接关系、来源证据和历史版本。

### 修改知识

`PATCH /api/v1/knowledge/entities/{entity_id}`

第一版允许修改名称、摘要、确认状态和业务状态。所有修改记录操作人、时间和修改前内容。

### 合并实体

`POST /api/v1/knowledge/entities/merge`

```json
{
  "target_id": "保留的实体 ID",
  "source_ids": ["被合并实体 ID"],
  "reason": "名称和上下文一致"
}
```

## 搜索

### 搜索知识

`GET /api/v1/projects/{project_id}/search`

查询参数：

- `q`：查询文本。
- `mode`：`keyword`、`vector` 或 `hybrid`。
- `types`：可选实体类型。
- `valid_at`：可选时间点。
- `top_k`：默认 10。

每条结果返回关键词得分、向量得分、图关系得分和最终融合得分，便于实验分析。

## 证据问答

### 创建问答请求

`POST /api/v1/projects/{project_id}/questions`

```json
{
  "question": "事件驱动架构在哪些代码中实现？",
  "center_entity_id": "可选中心节点",
  "valid_at": null
}
```

普通响应可以直接返回完整结果；流式实现建议使用 Server-Sent Events。

```json
{
  "id": "...",
  "answer": "...",
  "confidence": 0.88,
  "entities": ["..."],
  "evidence": [
    {
      "id": "...",
      "title": "DomainEvent.java",
      "uri": "project://commerce-core/domain/DomainEvent.java",
      "locator": { "start_line": 12, "end_line": 28 },
      "excerpt": "..."
    }
  ],
  "retrieval": {
    "keyword_hits": 3,
    "vector_hits": 6,
    "graph_hits": 4
  },
  "missing_information": []
}
```

证据不足时 `answer` 应明确表达无法确认，`missing_information` 返回需要补充的资料，不能编造结论。

## 人工确认

### 查询待确认项目

`GET /api/v1/projects/{project_id}/reviews`

支持按候选类型、置信度和来源筛选。

### 确认或拒绝候选

`POST /api/v1/reviews/{review_id}/resolve`

```json
{
  "action": "confirm",
  "changes": {
    "name": "规范化后的名称"
  }
}
```

`action` 允许 `confirm`、`reject` 和 `merge`。

## 第一版接口优先级

1. 项目创建与查询。
2. Markdown 上传与任务状态。
3. 候选知识查询与确认。
4. 局部图谱和节点详情。
5. 混合搜索。
6. 证据问答。
7. 历史状态和替代关系查询。
