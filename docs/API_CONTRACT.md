# Knowledge Atlas 前后端接口草案

本文定义第一版前后端协作所需的最小接口。项目、Markdown 来源、任务、健康检查、候选提取、基础审核和图谱接口已经实现；检索和问答接口仍是设计草案。字段调整时应保持错误结构和分页结构一致。

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
| `GET /api/v1/sources/{source_id}/extraction` | 已实现，读取候选提取任务状态 |
| `POST /api/v1/sources/{source_id}/extract` | 已实现，显式 DeepSeek 候选提取 |
| `GET /api/v1/projects/{project_id}/reviews` | 已实现，分页候选查询 |
| `POST /api/v1/reviews/{review_id}/resolve` | 已实现，确认/拒绝及名称摘要修正，确认时写入正式图谱 |
| `GET /api/v1/projects/{project_id}/graph` | 已实现，只读局部图谱 |
| `GET /api/v1/knowledge/entities/{entity_id}` | 已实现，实体详情、证据与直接关系 |
| `GET /api/v1/knowledge/relationships/{relationship_id}` | 已实现，关系详情与证据 |
| 搜索和问答接口 | 规划中 |

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

状态：已实现，只读。只返回当前用户有效项目中的未归档知识，并按 `valid_at` 过滤生效区间。

查询参数：

- `center_id`：中心节点，可选。
- `depth`：关系深度，只允许 1 或 2。
- `types`：逗号分隔的实体类型。
- `valid_at`：查询指定时间点的有效知识，必须是带时区时间。
- `limit`：最大节点数，1–200，默认 100；边最多返回 500 条。

```json
{
  "nodes": [
    {
      "id": "...",
      "project_id": "...",
      "candidate_id": "...",
      "type": "Concept",
      "name": "事件驱动架构",
      "summary": "围绕事件组织系统组件的架构方式",
      "confidence": 0.96,
      "status": "active",
      "valid_from": "2024-05-01T00:00:00+08:00",
      "valid_to": null,
      "evidence_count": 3
    }
  ],
  "edges": [
    {
      "id": "...",
      "project_id": "...",
      "candidate_id": "...",
      "type": "IMPLEMENTED_BY",
      "name": "事件驱动架构 → 订单服务",
      "summary": "订单服务实现事件驱动架构",
      "source_id": "...",
      "target_id": "...",
      "confidence": 0.91,
      "status": "active",
      "valid_from": "2024-05-01T00:00:00+08:00",
      "valid_to": null,
      "evidence_count": 1
    }
  ],
  "truncated": false
}
```

节点坐标不属于领域接口。前端自行计算布局；如需保存个人布局，使用独立视图配置接口。

### 查询实体详情

`GET /api/v1/knowledge/entities/{entity_id}`

状态：已实现，只读。返回 `entity`、`evidence`、`relationships` 和 `truncated`。证据包含 `id`、`source_id`、`chunk_id`、`title`、`uri`、`quote`、`start_line`、`end_line`、`heading_path`；直接关系最多返回 100 条。

### 查询关系详情

`GET /api/v1/knowledge/relationships/{relationship_id}`

状态：已实现，只读。返回 `relationship` 及其 `evidence`，字段与实体详情中的证据一致。

两个详情接口也支持带时区的 `valid_at`；关系及两端实体必须在该时刻可见。不可访问或不可见的知识返回 HTTP 404 `KNOWLEDGE_NOT_FOUND`；归档或不可访问项目沿用项目接口的 404。图谱类型非法返回 HTTP 422 `GRAPH_TYPES_INVALID`，确认时类型、端点或证据校验失败返回 HTTP 409 `KNOWLEDGE_PROMOTION_INVALID`，所有错误沿用统一 `error` 结构。

### 修改知识（规划中）

`PATCH /api/v1/knowledge/entities/{entity_id}`

第一版允许修改名称、摘要、确认状态和业务状态。所有修改记录操作人、时间和修改前内容。

### 合并实体（规划中）

`POST /api/v1/knowledge/entities/merge`

```json
{
  "target_id": "保留的实体 ID",
  "source_ids": ["被合并实体 ID"],
  "reason": "名称和上下文一致"
}
```

## 搜索

状态：规划中，当前未实现。

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

状态：规划中，当前未实现；页面中的问答为演示数据。

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

### 显式候选提取

`POST /api/v1/sources/{source_id}/extract` 无请求体，同步返回：

```json
{
  "task": {
    "id": "...",
    "type": "knowledge_candidates",
    "status": "succeeded",
    "stage": "candidates_ready",
    "progress": 100
  },
  "candidate_count": 3
}
```

`task` 实际包含任务查询接口的全部字段，上例仅展示关键字段。上传产生的解析任务及项目资料列表的 `task_id` 保持不变；候选提取使用另一任务。`GET /api/v1/sources/{source_id}/extraction` 返回同一结构；尚未提取时 `task` 为 `null`、数量为 0，不会调用模型。

仅允许当前用户有效项目内已解析且有分块的资料；未解析或无分块返回 HTTP 409，未配置密钥返回 HTTP 503，输入超过默认 100 个分块/序列化 JSON 60000 字符返回 HTTP 413，不会截断资料。成功结果按来源/提示版本复用，不再调用模型。正在执行且租约有效时返回 HTTP 409 `EXTRACTION_RUNNING`；租约过期允许显式接手，旧执行写入返回 HTTP 409 `EXTRACTION_REPLACED`。解析 Worker 不消费候选任务。

模型连接/认证/余额/限流错误、无效 JSON、未完整结束的输出或伪造引用，返回 HTTP 200 和 `failed` 任务，`error.code` 为 `EXTRACTION_PROVIDER_FAILED`、`EXTRACTION_OUTPUT_INVALID` 或 `EXTRACTION_EVIDENCE_INVALID`。不保存部分候选，不改变资料已解析状态，不暴露原始模型错误或密钥。失败可手动重试；不自动重试或强制重新提取成功批次。

### 查询候选知识

`GET /api/v1/projects/{project_id}/reviews`

分页返回 `items`、`page`、`page_size`、`total`，按创建时间、ID 稳定排序。`page >= 1`、`1 <= page_size <= 100`；支持 `source_id`、`review_status`（`pending`/`confirmed`/`rejected`）、`candidate_type` 和 `min_confidence`（0–1）。不传审核状态时包含所有候选，空列表或越界页返回空 `items`。不存在、其他用户或已归档项目返回 HTTP 404；来源筛选必须属于当前项目。

每项包含 `id`、`project_id`、`source_id`、`task_id`、`kind`（`entity`/`relation`）、`type`、`name`、`summary`、`confidence`、`review_status`、`created_at`、`updated_at` 及 `evidence`。证据包含 `chunk_id`、`quote`、准确 `start_line`/`end_line` 和 `heading_path`；行号由后端计算。关系另外包含同批实体的 `source_candidate_id`/`target_candidate_id`，实体对应字段为 `null`。不暴露操作者内部标识、密钥或模型原始响应。

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

`action` 当前只允许 `confirm` 和 `reject`。`changes` 可省略，只允许非空 `name`（最多 255 字符）和 `summary`（最多 2000 字符）；拒绝不能同时修改内容。返回更新后的候选对象，已确认时包含 `knowledge_id`；正式图谱对象通过图谱接口读取。确认时在同一事务内重新校验引用、写入正式实体/关系/证据，使用稳定 UUID 并按候选幂等。未处理候选只能处理一次，重复相同动作/相同修改返回原结果且不新增审核事件；改判或不同修改返回 HTTP 409 `REVIEW_ALREADY_RESOLVED`。关系确认前，两端同批实体必须已确认，否则 HTTP 409 `REVIEW_ENDPOINTS_UNCONFIRMED`。不可访问候选返回 HTTP 404。审核状态、`review_events` 前后记录和正式图谱写入同一事务提交。

已确认但尚未生成正式记录的旧候选，可再次提交相同确认进行补写；该重放不重复模型调用，也不新增审核事件。当前不支持 `merge`、撤销、修改类型/证据/端点；实体消歧、检索和问答仍属于后续设计。

## 第一版接口优先级

1. 项目创建与查询。
2. Markdown 上传与任务状态。
3. 候选知识查询与确认。
4. 局部图谱和节点详情。
5. 混合搜索。
6. 证据问答。
7. 历史状态和替代关系查询。
