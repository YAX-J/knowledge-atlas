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
| `GET /api/v1/projects/{project_id}/sources` | 已实现，分页查询项目资料及最新任务 |
| `GET /api/v1/sources/{source_id}` | 已实现 |
| `GET /api/v1/tasks/{task_id}` | 已实现 |
| `POST /api/v1/tasks/{task_id}/run` | 已实现，同步执行 Markdown 解析 |
| `GET /api/v1/sources/{source_id}/chunks` | 已实现，分页查询原文分块 |
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

## 健康检查

`GET /api/v1/health/live` 检查进程存活，不访问数据库。

`GET /api/v1/health/ready` 当前只检查 PostgreSQL 连接，不要求独立图数据库：

```json
{
  "status": "ready",
  "dependencies": {
    "postgresql": { "status": "up", "detail": null }
  }
}
```

连接失败时返回 HTTP 503，顶层 `status` 为 `degraded`，PostgreSQL 的 `status` 为 `down`、`detail` 为 `database connection failed`，不暴露连接凭据或异常细节。依赖状态仅包含 `up` 和 `down`。就绪检查不验证 pgvector 扩展、迁移版本或业务流程；这些仍需单独验收。

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

### 查询项目资料

`GET /api/v1/projects/{project_id}/sources?page=1&page_size=20`

返回 `items`、`page`、`page_size`、`total`，按上传时间降序、ID 稳定排序。每条资料包含 `id`、`project_id`、`original_name`、`size_bytes`、来源 `status`、`created_at`、`updated_at`，以及当前用户/项目下最新任务的 `task_id` 和 `task_status`（无任务时为 `null`）。列表不返回原文或预览内容，详情从来源接口读取。

`page >= 1`，`1 <= page_size <= 100`。空项目或越过最后一页返回空列表；项目不存在、已归档或不属于当前用户时返回 HTTP 404。

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

同一用户、同一项目中，相同文件字节（SHA-256 一致）的重复上传会复用已有 `source_id` 与 `task_id`，不受文件名影响。始终返回 HTTP 202；`status` 为复用任务的当前状态，因此也可能是 `running`、`succeeded`、`failed` 或 `cancelled`。原文件名保留首次上传值。内容变化或项目不同会创建独立来源，不自动替换旧来源。

### 查询任务状态

`GET /api/v1/tasks/{task_id}`

```json
{
  "id": "...",
  "project_id": "...",
  "source_id": "...",
  "type": "markdown_parsing",
  "status": "succeeded",
  "stage": "parsed",
  "progress": 100,
  "error": null,
  "created_at": "2026-10-17T14:30:00+08:00",
  "updated_at": "2026-10-17T14:30:01+08:00",
  "started_at": "2026-10-17T14:30:01+08:00",
  "completed_at": "2026-10-17T14:30:01+08:00"
}
```

任务状态建议使用：`queued`、`running`、`succeeded`、`failed`、`cancelled`。

### 执行解析任务

`POST /api/v1/tasks/{task_id}/run`

无需请求体，同步返回与任务查询相同的结构。上传事务只排队；启动独立 Worker 后会自动消费，也可通过此接口手动执行。旧版 `knowledge_extraction` 上传任务也只执行解析，不调用模型。

- `queued` 或 `failed`：原子认领后进入 `running` / `parsing`，成功后为 `succeeded` / `parsed` / 100，来源变为 `ready`。
- `succeeded`：直接返回原结果，不重复创建分块。
- `running` 或 `cancelled`：HTTP 409，错误码 `TASK_NOT_RUNNABLE`。
- 解析或分块写入失败：HTTP 200，任务为 `failed`，`error.code` 为 `SOURCE_PARSE_FAILED`，来源为 `failed`；不会保留本次不完整分块，可再次调用重试。
- 当前用户无法访问的任务：HTTP 404。

### 后台消费与中断恢复

启动 `python -m app.worker` 后，后台进程会在指定用户的有效项目内消费 `queued` 任务，并接手租约过期的 `running` 任务。执行 UUID、租约截止时间和尝试次数是内部持久化字段，不改变现有 HTTP 响应结构。旧执行不能覆盖被接手后的成功或失败状态和分块。

默认执行租约 300 秒，最多自动尝试 3 次；达到次数上限的过期任务变为 `failed`，`error.code` 为 `TASK_ATTEMPTS_EXHAUSTED`，需要手动重试。普通 `SOURCE_PARSE_FAILED` 不会自动重试。旧任务无租约时根据开始时间或更新时间判断超时。手动接口对所有 `running` 任务仍返回 HTTP 409，恢复由 Worker 执行。

Worker 与手动执行竞争时，只有认领成功的一方执行；另一方可能得到当前成功结果或 HTTP 409，客户端可刷新状态。前端当前通过“刷新状态”读取后台结果，尚未自动轮询。运行方式与限制见 [后端说明](../backend/README.md)。

### 查询资料原文

`GET /api/v1/sources/{source_id}`

返回资料元数据、SHA-256、解析状态、行数和最多 4000 字符的可预览内容，不返回服务器文件路径。

### 查询资料分块

`GET /api/v1/sources/{source_id}/chunks?page=1&page_size=20`

`page >= 1`，`1 <= page_size <= 100`。按原文顺序返回 `items`、`page`、`page_size`、`total`。未解析来源返回空列表；不存在或不属于当前用户的来源返回 HTTP 404。

`items` 中每条记录包含：`id`、`project_id`、`source_id`、从 0 开始的 `position`、`kind`（`heading`、`paragraph`、`list`、`code`）、`heading_path`、从 1 开始且包含两端的 `start_line` / `end_line`、原始 `content` 和 `content_sha256`。原文换行符保留，哈希为该片段 UTF-8 字节的 SHA-256。同一来源中相同边界和内容的分块 UUID 稳定。标题块的路径包含自身；正文块继承其所在标题路径。

当前解析范围为 ATX/Setext 标题、段落、列表和围栏代码块，其余语法作为文本保留，尚未提供完整 CommonMark 语法树。

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
