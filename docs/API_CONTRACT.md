# Knowledge Atlas 前后端接口草案

## 多语言代码解析（已实现）

- 上传新增 Python、JavaScript/JSX、TypeScript/TSX、Go、C、C++、C#，详见[扩展名和边界](MULTILANGUAGE_PARSING.zh-CN.md)。`source_type` 省略时由扩展名推断，显式填写仍须匹配。复用 `code_parsing`，无新迁移。
- `GET /sources/{source_id}/code-structure` 对全部支持代码有效，返回 `language`、`has_syntax_errors` 与共用 `symbols`（`type/field/method`）。Java 继续返回本地确定性调用关系；其他语言默认不产生跨文件关系。
- `POST /sources/{source_id}/agent-call-analysis?strategy=single_step|tools` 显式分析 Java、Python、JavaScript/JSX、TypeScript/TSX、Go、C/C++、C# 的同仓库跨文件候选。默认单轮，可选有界工具循环。没有候选时不调用模型；结果不持久化、不写正式图谱。
- `GET /projects/{project_id}/code-symbols` 扫描全部支持代码，命中增加 `language`，响应增加 `has_syntax_errors`。语法错误与 `truncated` 独立，权限/仓库/数量上限不变。
- GitHub 同步新增可选 `rescan:boolean=false`，例如 `{"ref":"main","rescan":true}`，重读同 Commit tree 以发现旧快照未记录的新语言；复用兼容 blob，仍遵守原预算和历史非破坏规则。默认继续完整同提交缓存。

本文定义第一版前后端协作所需的最小接口。项目、Markdown/Java 来源、任务、健康检查、候选提取、审核、图谱、关键词/语义向量/一跳图关系混合检索及同步证据问答接口已经实现。字段调整时应保持错误结构和分页结构一致。

## 时序演化与只读治理（已实现）

须先应用迁移 `20261023_0015`。以下路径均以 `/api/v1` 开头，限定当前用户及未归档项目，不暴露 `user_id`。

- `POST /projects/{project_id}/knowledge-changes`：JSON 为 `new_entity_id,old_entity_id,evidence_id,kind,reason,effective_at`；`kind` 为 `SUPERSEDES/SUPPLEMENTS/CONFLICTS_WITH`，理由非空且最多 2000 字符，时间须带时区。两端为本项目不同、同类型、`active` 且无截止时间的正式实体；双方保留有效逐字证据，所选证据属于任一端点。时间不早于双方有效起点、不晚于当前时刻。返回 HTTP 200 待审核记录；规范化后相同请求复用 UUID/原状态，不自动确认。
- `GET /projects/{project_id}/knowledge-changes?review_status=pending&page=1&page_size=20`：可选 `pending/confirmed/rejected`，每页 1–100。返回 `items,total,page,page_size`，按创建时间倒序/UUID 排序。
- `POST /projects/{project_id}/knowledge-changes/{change_id}/resolve`：`{"action":"confirm"}` 或 `reject`。项目锁内重新校验，同事务记录审核及前后快照。重复同动作幂等，改判 409。确认替代才设置 `old.status=superseded`、`old.valid_to=new.valid_from=effective_at`；补充/冲突仅记录分类，不改有效期。不支持分叉、合并、环或失效端点。
- 记录字段：`id,project_id,new_entity_id,old_entity_id,evidence_id,new_entity_name,old_entity_name,kind,reason,effective_at,review_status,resolved_at,created_at,before,after,evidence`。快照为不可变双端点状态/有效期，证据沿用正式结构，可跳精确分块。时间统一 UTC，原文不覆盖。
- `GET /projects/{project_id}/knowledge/entities/{entity_id}/history`：返回 `entities,changes,truncated`。忽略当前有效期，不忽略用户/项目/归档；双向遍历已确认替代，按有效起点/生效时间排序，最多 100 个实体/200 条变化。普通图谱不加入失效端点；演化链与语义关系独立。
- `GET /projects/{project_id}/governance?limit=200`：只读、无模型、无持久化；最多扫描 1000 个当前实体，默认最多 200 条建议、最大 500。返回 `checked_at,scanned_entity_count,truncated,findings`，每条含稳定 `id`、`kind`（`missing_evidence/duplicate/possible_conflict/orphan`）、`entity_ids,message,entities`，entities 含 id/name/summary/type，供画布外知识核对。同类型名称经 NFKC/大小写/空白规范化，在各摘要组内识别重复；各新摘要组与名称组首项作可能冲突提示。先返回缺失证据、重复、可能冲突，最后孤立建议；扫描有界，非完整语义判定。

作用域缺失 404。`CHANGE_STALE`、`CHANGE_EVIDENCE_INVALID`、`CHANGE_TIME_INVALID`、`CHANGE_ENDPOINTS_INVALID`、`CHANGE_CHAIN_INVALID`、`CHANGE_ALREADY_RESOLVED` 均为 409。结构、枚举、无时区时间或额外字段返回统一 422。历史沿用图谱/详情/搜索/问答的 `valid_at`；有效区间半开 `[valid_from,valid_to)`，不能按当前 `status == active` 排除历史上仍有效的已替代实体。前端图谱和搜索使用同一时间上下文。

## 实现状态

| 接口 | 状态 |
| --- | --- |
| `GET /api/v1/health/live` | 已实现 |
| `GET /api/v1/health/ready` | 已实现 |
| `GET/POST /api/v1/projects` | 已实现 |
| `GET /api/v1/projects/{project_id}` | 已实现 |
| `POST /api/v1/projects/{project_id}/repositories/resolve` | 已实现，幂等解析本地文件夹仓库身份 |
| `POST /api/v1/projects/{project_id}/repositories/resolve-github` | 已实现，规范化并登记 GitHub remote 身份 |
| `POST /api/v1/projects/{project_id}/repositories/{repository_id}/sync-github` | 已实现，显式导入有界 GitHub 快照 |
| `POST /api/v1/projects/{project_id}/repositories/{repository_id}/import-github-work-items` | 已实现，显式导入有界 GitHub Issue/PR 与 PR Review 活动版本 |
| `GET /api/v1/projects/{project_id}/repositories/{repository_id}/snapshots` | 已实现，分页查询持久化 Commit 快照历史 |
| `GET /api/v1/projects/{project_id}/repositories/{repository_id}/snapshots/{snapshot_id}/files` | 已实现，分页查询快照逐文件来源和有效资料跳转 |
| `POST /api/v1/projects/{project_id}/repositories/{repository_id}/snapshots/{snapshot_id}/commit-source` | 已实现，将已保存提交说明导入/复用为 Markdown 资料与任务 |
| `GET /api/v1/projects/{project_id}/repositories` | 已实现，分页查询来源仓库 |
| `POST /api/v1/projects/{project_id}/sources` | 已实现，Markdown 与 Java 源文件 |
| `GET /api/v1/projects/{project_id}/sources` | 已实现，分页查询项目资料及最新任务 |
| `GET /api/v1/sources/{source_id}` | 已实现 |
| `GET /api/v1/tasks/{task_id}` | 已实现 |
| `POST /api/v1/tasks/{task_id}/run` | 已实现，同步执行 Markdown/Java 解析 |
| `GET /api/v1/sources/{source_id}/chunks` | 已实现，分页查询原文分块 |
| `GET /api/v1/sources/{source_id}/code-structure` | 已实现，派生 Java 符号、同文件调用及有界跨文件类型/方法关系 |
| `POST /api/v1/sources/{source_id}/agent-call-analysis` | 已实现，显式执行有界多语言 Agent 跨文件候选分析与证据校验 |
| `GET /api/v1/projects/{project_id}/code-symbols` | 已实现，按名称/路径与仓库/类型检索已解析多语言代码符号 |
| `GET /api/v1/sources/{source_id}/extraction` | 已实现，读取候选提取任务状态 |
| `POST /api/v1/sources/{source_id}/extract` | 已实现，显式 DeepSeek 候选提取 |
| `GET /api/v1/projects/{project_id}/reviews` | 已实现，分页候选查询 |
| `POST /api/v1/reviews/{review_id}/resolve` | 已实现，确认/拒绝及名称摘要修正，确认时写入正式图谱 |
| `GET /api/v1/projects/{project_id}/graph` | 已实现，只读局部图谱 |
| `GET /api/v1/knowledge/entities/{entity_id}` | 已实现，实体详情、证据与直接关系 |
| `GET /api/v1/knowledge/relationships/{relationship_id}` | 已实现，关系详情与证据 |
| `POST /api/v1/projects/{project_id}/embeddings/rebuild` | 已实现，显式生成或复用正式实体向量 |
| `GET /api/v1/projects/{project_id}/search` | 已实现，正式实体关键词/向量/一跳图关系混合检索与证据 |
| `POST /api/v1/projects/{project_id}/questions` | 已实现，同步、非持久化的证据问答 |

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

### 解析与查询本地来源仓库

`POST /api/v1/projects/{project_id}/repositories/resolve`

```json
{
  "name": "commerce-core",
  "kind": "local_folder"
}
```

`name` 为浏览器文件夹选择提供的单个根目录名，去除首尾空白后长度为 1–255，不得为 `.` / `..`，也不得包含路径分隔符、NUL 或换行。当前 `kind` 只允许 `local_folder`。接口按当前用户、项目、类型和名称幂等返回稳定仓库 UUID；相同输入不会重复创建。

`POST /api/v1/projects/{project_id}/repositories/resolve-github`

```json
{
  "remote_url": "git@github.com:example/commerce-core.git",
  "local_repository_id": null
}
```

接受 `https://github.com/owner/repository`、`git@github.com:owner/repository.git` 与 `ssh://git@github.com/owner/repository.git`，把 owner/name 转为小写并返回规范化 `https://github.com/owner/repository`。`local_repository_id` 可选；提供时必须是当前用户/项目中尚未关联 remote，或已关联同一身份的 `local_folder`，否则创建或复用 `kind=git_remote` 的仅远程记录。接口只登记身份，不访问 GitHub、不验证仓库存在性，也不克隆文件。

非 GitHub、包含查询参数/片段、HTTPS 凭据或格式不合法的地址返回 HTTP 422 `GITHUB_REMOTE_INVALID`。本地仓库已关联其他 remote 返回 HTTP 409 `SOURCE_REPOSITORY_REMOTE_CONFLICT`；remote 已登记到另一条仓库记录返回 HTTP 409 `GITHUB_REPOSITORY_ALREADY_REGISTERED`；把 remote 关联到非本地仓库返回 HTTP 409 `SOURCE_REPOSITORY_NOT_LOCAL`。越过用户/项目边界仍返回 HTTP 404。

`GET /api/v1/projects/{project_id}/repositories?page=1&page_size=20` 分页返回 `id`、`project_id`、`name`、`kind`、可空的 `provider` / `provider_repository_id` / `remote_owner` / `remote_name` / `remote_url`、`created_at` 与 `updated_at`。`provider_repository_id` 在首次成功联系 GitHub 后保存；GitHub 返回的新规范 owner/name 会更新 remote 坐标，但稳定 provider ID 不得变化。项目不可访问时返回 HTTP 404。

### 同步 GitHub 仓库快照

`POST /api/v1/projects/{project_id}/repositories/{repository_id}/sync-github`

```json
{
  "ref": "main"
}
```

`ref` 可省略；省略时读取仓库默认分支，也可填写 branch、tag 或 commit SHA。仓库必须已登记或关联 `provider=github`。后端通过 GitHub REST 解析 commit 与递归 tree，按路径顺序选择最多 50 份注册表支持的 Markdown/多语言代码文件，单份仍受 `MAX_UPLOAD_BYTES` 限制，一次同步累计下载最多 20 MiB。公开仓库无需令牌；私有仓库可在后端配置只读 `GITHUB_TOKEN`。

```json
{
  "repository_id": "...",
  "snapshot_id": "...",
  "ref": "main",
  "commit_sha": "0123456789abcdef...",
  "commit_url": "https://github.com/example/repository/commit/0123456789abcdef...",
  "imported_count": 2,
  "reused_count": 1,
  "unchanged_count": 4,
  "renamed_count": 1,
  "deleted_count": 1,
  "skipped_count": 1,
  "truncated": false,
  "deletion_detection_complete": true,
  "items": [
    {
      "path": "src/main/java/example/App.java",
      "previous_path": null,
      "source_id": "...",
      "task_id": "...",
      "status": "imported",
      "error_code": null
    }
  ]
}
```

每次新 Commit 或不完整快照重试会持久化 Commit/tree 元数据和逐文件 blob 映射，并以上一份同 ref 快照作为增量基线。`status` 可为 `imported`、`reused`、`unchanged`、`renamed`、`deleted` 或 `skipped`；未变化和可复用 blob 仅在来源类型及解析任务兼容、用户/项目/仓库一致时避免下载。完整文件集合中唯一旧路径消失且同类型 blob 未变时报告 `renamed`，完整 tree 中消失的旧路径报告 `deleted`。跨 Markdown/Java 类型变化会创建或复用正确类型的来源/任务，不把不兼容来源重命名。远端删除只记录快照变化，不物理删除历史来源、分块、知识或证据。

连续相同 Commit 仅在快照未截断、删除检测完整、成功引用兼容且没有大小类跳过时复用同一个 `snapshot_id`，不读取 tree/blob。确定性的空文件、非法编码/路径跳过不妨碍短路。否则再次调用同一接口会重读 tree，复用成功文件并尝试遗漏项，保存新的 `snapshot_id`；旧快照保留。每次仍最多选择 50 份文件、下载 20 MiB，不增加分页或自动重试；固定 50 文件上限不会因重复操作而绕过。普通失败解析任务仍通过原任务重试接口处理。详见 [ADR 0031](adr/0031-recoverable-typed-github-snapshots.zh-CN.md)。

空文件、非 UTF-8、非法路径或超限文件会按项跳过，已成功项不会回滚。`truncated=true` 表示 GitHub tree 自身截断、支持文件超过 50 份，或达到累计字节预算；此时 `deletion_detection_complete=false`，不会猜测删除。tree/文件选择截断时也不推断重命名。复制文件或同 blob 多路径存在歧义时只复用来源，不猜测重命名。

未关联 GitHub 的仓库返回 HTTP 409 `GITHUB_REPOSITORY_REQUIRED`；远端仓库/ref 不存在或无权读取返回 HTTP 404 `GITHUB_REPOSITORY_UNAVAILABLE`；GitHub 限流/拒绝返回 HTTP 503 `GITHUB_RATE_LIMITED`；网络、响应结构或其他供应商错误返回 HTTP 502 `GITHUB_PROVIDER_FAILED`。Blob 使用 GitHub raw 媒体类型流式读取，并在接收过程中执行单份大小限制。所有错误均不会暴露令牌或原始远端响应。

### 导入 GitHub Issue 与 Pull Request

`POST /api/v1/projects/{project_id}/repositories/{repository_id}/import-github-work-items`

```json
{
  "state": "all",
  "item_type": "all",
  "include_comments": true,
  "include_reviews": true,
  "include_review_threads": true,
  "limit": 20
}
```

仓库必须已关联 `provider=github`。`state` 可为 `all`、`open`、`closed`；`item_type` 可为 `all`、`issue`、`pull_request`；`limit` 为 1–20。后端按 GitHub `updated` 倒序读取一个有界候选页，最多导入 20 项；启用普通评论时，每项最多读取 20 条 Issue 评论。Pull Request 额外包含可获得的 head、base 与 merged 元数据。`include_reviews=true` 时，每个入选 PR 还读取最多 20 条 Review 和 20 条行级 Review Comment，并用 GitHub `Link` 响应头报告各自的截断状态。`include_review_threads=true` 时，若后端配置了 `GITHUB_TOKEN`，再通过 GraphQL 读取最多 20 个 Review thread 及每个 thread 最多 20 个评论标识，保存当前解决状态、解决者、位置、过期状态和评论成员关系。正文、评论与 Review 活动被确定性渲染为 Markdown，随后复用现有仓库范围去重、`markdown_parsing` 任务与人工审核链路。

```json
{
  "repository_id": "...",
  "imported_count": 2,
  "reused_count": 1,
  "skipped_count": 0,
  "review_imported_count": 1,
  "review_reused_count": 0,
  "review_skipped_count": 0,
  "truncated": false,
  "items": [
    {
      "number": 17,
      "item_type": "issue",
      "title": "记录重试决策",
      "html_url": "https://github.com/example/repository/issues/17",
      "source_id": "...",
      "task_id": "...",
      "status": "imported",
      "comments_truncated": false,
      "review_source_id": null,
      "review_task_id": null,
      "review_status": "not_requested",
      "reviews_count": 0,
      "review_comments_count": 0,
      "reviews_truncated": false,
      "review_comments_truncated": false,
      "review_threads_status": "not_requested",
      "review_threads_count": 0,
      "resolved_review_threads_count": 0,
      "review_threads_truncated": false,
      "error_code": null,
      "review_error_code": null
    }
  ]
}
```

GitHub provider item ID、`updated_at` 与 `include_comments` 组合标识工作项不可变版本。相同版本与评论配置重复导入返回 `reused`，远端更新或评论配置变化则创建新版本记录，不覆盖旧来源或证据。PR Review 活动保存为独立来源，以 provider PR ID 和渲染内容 SHA-256 标识版本，因此 Review、行级评论或 thread 当前状态变化时即使 PR `updated_at` 未变也会创建新快照。`review_threads_status` 为 `included`、`token_required` 或 `not_requested`；缺少令牌不会使 REST Review 导入失败，也不会把未读取误报为空线程。超过单份资料大小限制等本地导入错误分别在工作项或 Review 状态中返回 `skipped`；`truncated=true` 仅表示工作项候选达到有界读取上限，各 Review 截断字段独立报告，其中 `review_threads_truncated` 同时表示 thread 或其评论成员关系存在后续页。资料、图谱、搜索和问答中的 `git_url` 对两类来源都指向规范 Issue/PR 会话；行号仍定位本地保存的 Markdown 快照，不伪造 GitHub 会话行号片段。行级评论的 `in_reply_to_id` 与 GraphQL thread 评论标识会保留；连续快照可观察状态变化，但查询 API 不提供权威 resolved/unresolved 事件时间。附件、reaction、完整分页、Webhook、轮询与远端删除传播尚未实现。供应商错误沿用仓库快照接口的 `GITHUB_REPOSITORY_UNAVAILABLE`、`GITHUB_RATE_LIMITED` 与 `GITHUB_PROVIDER_FAILED`。

### 已保存提交说明转资料

`POST /api/v1/projects/{project_id}/repositories/{repository_id}/snapshots/{snapshot_id}/commit-source` 无请求体，返回 HTTP 200：

```json
{
  "snapshot_id": "snapshot-uuid",
  "source_id": "source-uuid",
  "task_id": "task-uuid",
  "status": "queued",
  "reused": false,
  "git_url": "https://github.com/example/project/commit/0123456789012345678901234567890123456789"
}
```

仅使用本用户、未归档项目及对应仓库中已保存的 GitHub 快照，不访问 GitHub 或模型。SHA（40/64 位十六进制）、UTC 提交时间和逐行引用的提交说明生成确定性 Markdown；ref、同步统计及可变 remote 坐标不参与内容摘要。文件名 `commit-{sha}.md`，相对路径 `github/commits/commit-{sha}.md`；空说明仍生成带来源边界的资料。相同仓库相同字节复用普通资料/解析任务，返回任务当前状态；无效/缺失映射重新走导入去重，不信任跨作用域或不兼容任务引用。大小限制沿用 `MAX_UPLOAD_BYTES`，超限为 413 `SOURCE_TOO_LARGE`，不写映射或半份资料。

快照不存在/跨用户/项目/仓库或项目归档返回 404；仓库未关联 GitHub 返回 409 `GITHUB_REPOSITORY_REQUIRED`，无效 SHA 返回 409 `SNAPSHOT_COMMIT_INVALID`。成功会补充当前快照可空 `commit_source_id` / `commit_task_id`，不修改原有提交/文件同步事实。首次状态通常为 `queued`，不自动解析、抽取或审核；Worker 仍可消费普通解析任务。资料与正式图谱/搜索/问答证据派生规范 `/commit/{sha}`，不追加 Markdown 行号到 GitHub Commit 页面。`project://` 与本地分块行号不变；该来源不是 diff/变更文件清单，也不能证明说明中的结论成立。见 [ADR 0033](adr/0033-saved-commit-evidence-sources.zh-CN.md)。

### 查询仓库 Commit 快照

`GET /api/v1/projects/{project_id}/repositories/{repository_id}/snapshots?page=1&page_size=20`

按创建时间倒序返回 `items`、`page`、`page_size` 与 `total`。每份快照包含 `id`、`repository_id`、`ref`、`commit_sha`、`tree_sha`、可空 `commit_url` / `committed_at`、`commit_message`、文件及各类变更计数、`downloaded_bytes`、`truncated`、`deletion_detection_complete` 与 `created_at`。接口不返回文件原文或后端令牌；越过用户/项目/仓库边界返回 HTTP 404。

每份快照另返回可空的 `commit_source_id` / `commit_task_id`，供前端显示“加入资料/打开资料”；只有显式提交说明导入后才补充，不触发远端读取。项目已归档也返回 404。

### 查询快照逐文件来源

`GET /api/v1/projects/{project_id}/repositories/{repository_id}/snapshots/{snapshot_id}/files?page=1&page_size=20` 只读本地同步记录，不访问 GitHub 或模型。`page >= 1`，每页 1–100（默认 20），按 `path`、UUID 稳定排序。返回 `snapshot_id`、`repository_id`、`commit_sha`、`truncated`、`deletion_detection_complete`、`items`、`page`、`page_size`、`total`。每项字段：

- `id`、`path`、可空 `previous_path`、`blob_sha`、`size_bytes`、可空 `error_code`。
- `status`：`imported` / `reused` / `unchanged` / `renamed` / `deleted` / `skipped`，保持保存时的同步事实；来源状态可能随后变化。
- 可空 `source_id`、`task_id`、`source_status`：只有本用户/项目/仓库且与路径来源类型兼容时提供来源跳转；任务还需匹配此来源及对应解析类型（包括旧 Markdown `knowledge_extraction`）。缺失、不兼容或跨作用域映射置空，仍保留原文件记录；跳过项不提供来源/任务跳转。ready 资料即使无有效任务也可打开原文。
- 可空 `git_url`：使用当前规范 remote，固定到所选快照的 Commit 和编码后的路径，不使用来源最近一次出现的快照。删除项不生成指向删除后 Commit 的文件 URL；合法保留来源仍可读取。非法路径/SHA 不生成外链，跳过项的合法远端文件仍可有外链。

`total` 包含已保存的删除/跳过记录，不等于 `file_count` 或完整仓库文件数；分页不会绕过原同步预算。空快照或超出最后一页返回空列表；不可访问/归档项目或快照不属于当前仓库/用户/项目返回 404。接口不返回原文、任务结果、服务器路径或令牌，也不写来源/任务/正式知识。它不是 patch/diff 或变更正确性证明。见 [ADR 0034](adr/0034-snapshot-file-provenance.zh-CN.md)。

### 查询项目资料

`GET /api/v1/projects/{project_id}/sources?page=1&page_size=20`

返回 `items`、`page`、`page_size`、`total`，按上传时间降序、ID 稳定排序。每条资料包含 `id`、`project_id`、可空的 `repository_id` / `repository_name`、`original_name`、可空的 `relative_path` / `git_url`、`source_type`、`size_bytes`、来源 `status`、`created_at`、`updated_at`，以及当前用户/项目下最新任务的 `task_id` 和 `task_status`（无任务时为 `null`）。列表不返回原文或预览内容，详情从来源接口读取。

`page >= 1`，`1 <= page_size <= 100`。空项目或越过最后一页返回空列表；项目不存在、已归档或不属于当前用户时返回 HTTP 404。

### 上传资料

`POST /api/v1/projects/{project_id}/sources`

表单字段：

- `file`：接受[注册表支持](MULTILANGUAGE_PARSING.zh-CN.md)的 UTF-8 Markdown/代码文件，默认最大 10 MiB。
- `source_type`：可选，未填写时由后缀识别；填写时必须与注册表根据后缀推断的来源类型一致。
- `repository_id`：可选，必须属于当前用户和项目；文件夹导入先通过仓库解析接口取得。
- `relative_path`：可选，供文件夹上传保存包含文件名的仓库内相对路径；最长 1024 字符，统一为 `/`，不得是绝对路径、包含空段、`.`/`..`，末段必须与上传文件名一致。提供 `repository_id` 时必填；单文件上传通常同时省略两者。

响应：

```json
{
  "source_id": "...",
  "task_id": "...",
  "status": "queued"
}
```

同一用户、同一项目、同一可空仓库和同一来源类型中，相同文件字节（SHA-256 一致）的重复上传会复用已有 `source_id` 与 `task_id`，不受文件名或相对路径影响；相同字节位于不同仓库时创建独立来源。始终返回 HTTP 202；`status` 为复用任务的当前状态，因此也可能是 `running`、`succeeded`、`failed` 或 `cancelled`。原文件名与 `relative_path` 保留首次上传值。来源类型、内容、仓库或项目不同会创建独立来源，不自动替换旧来源。无效相对路径返回 HTTP 422 `SOURCE_PATH_INVALID`；仓库来源缺少路径返回 `SOURCE_REPOSITORY_PATH_REQUIRED`；仓库不存在或越界返回 HTTP 404 `SOURCE_REPOSITORY_NOT_FOUND`。

### 查询任务状态

`GET /api/v1/tasks/{task_id}`

```json
{
  "id": "...",
  "project_id": "...",
  "source_id": "...",
  "type": "code_parsing",
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

无需请求体，同步返回与任务查询相同的结构。上传事务只排队；启动独立 Worker 后会自动消费，也可通过此接口手动执行。Markdown 使用 `markdown_parsing`，Java 使用 `code_parsing`；旧版 `knowledge_extraction` 上传任务也只执行 Markdown 解析，不调用模型。

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

返回资料元数据（包括可空的 `repository_id`、`repository_name`、`relative_path` 与 `git_url`）、SHA-256、解析状态、行数和最多 4000 字符的可预览内容，不返回服务器绝对路径。项目资料列表中的每项也返回相同语义的可空 `git_url`。GitHub 文件来源从最近一次非删除快照派生固定到 Commit 的文件 URL；GitHub 工作项与 PR Review 活动来源返回规范 Issue/PR 会话 URL；本地来源返回 `null`，远端文件后来删除时保留指向最后一次存在快照的链接。

### 查询资料分块

新增只读 `GET /api/v1/projects/{project_id}/sources/{source_id}/chunks/{chunk_id}`，按精确 UUID 获取单个已保存分块，返回与下方分页项相同的 `SourceChunkRead`（包括从 0 开始的 `position`），供图谱/搜索/问答证据跳转。校验未归档项目及来源、分块的用户/项目/来源关联；不存在或不匹配返回 404 `SOURCE_CHUNK_NOT_FOUND`（项目不可访问沿用项目 404），非法 UUID 为统一 422。不扫描文本、文件名或所有分块页，不要求解析任务仍存在，也不写数据或调用模型。前端以 `floor(position / 20) + 1` 读取既有分块分页并聚焦原 UUID；不能展示时提供错误/重试，不回退到同名资料。

`GET /api/v1/sources/{source_id}/chunks?page=1&page_size=20`

`page >= 1`，`1 <= page_size <= 100`。按原文顺序返回 `items`、`page`、`page_size`、`total`。未解析来源返回空列表；不存在或不属于当前用户的来源返回 HTTP 404。

`items` 中每条记录包含：`id`、`project_id`、`source_id`、从 0 开始的 `position`、`kind`、`heading_path`、从 1 开始且包含两端的 `start_line` / `end_line`、原始 `content` 和 `content_sha256`。Markdown 的 `kind` 为 `heading`、`paragraph`、`list` 或 `code`；Java 的 `kind` 为 `code`、`comment`、`type` 或 `method`。原文换行符保留，哈希为该片段 UTF-8 字节的 SHA-256。同一来源中相同边界和内容的分块 UUID 稳定。标题块的路径包含自身；正文块继承标题路径；Java 类型路径为 `[类型]`，方法路径为 `[类型, 方法]`。顶层类型前连续的注解行归入类型；方法外只含注释的行单独标记为 `comment`。

Markdown 当前解析 ATX/Setext 标题、段落、列表和围栏代码块，其余语法作为文本保留。Java 当前识别顶层类型和常规直接成员方法，并保留其余源码；不提供完整 Java AST、嵌套类型语义、重载签名、完整调用图或仓库增量同步。边界见 [ADR 0012](adr/0012-bounded-java-source-ingestion.zh-CN.md)。

### 检索多语言代码符号

`GET /api/v1/projects/{project_id}/code-symbols?q=save&kind=method&limit=50`

必填 `q` 为 1–200 字符，去掉首尾空白后按本地大纲限定名（例如 `OrderService.save`）或来源路径进行不区分大小写的字面子串匹配，不把 `%`、`_` 当 SQL 通配符。可选 `repository_id` 限定当前用户/项目的仓库；省略时包含该项目所有仓库及未归属资料。`kind` 可为 `type`、`field`、`method`；`limit` 默认为 50、范围 1–100。只读取 `ready` 的受支持代码来源，不调用模型或构建工具、不写正式知识。

返回 `query`、`items`、`scanned_source_count`、`matched_count`、`truncated` 和 `has_syntax_errors`。命中另含 `language`。每项包含原大纲符号 `id`/`kind`/`name`/`qualified_name`/`owner`/包含式 `start_line`、`end_line`，以及 `source_id`、`source_path`、可空的 `repository_id`、`repository_name`、`task_id`、`chunk_id`、`chunk_position`、`git_url`。`chunk_position` 从 0 开始；前端使用资料分块接口默认每页 20 条计算目标页并聚焦对应 `chunk_id`。GitHub 文件 URL 固定到 Commit 和声明行，本地资料为 null。历史来源版本保持独立，不合并同名符号。

按来源创建时间和 UUID 确定最多 100 份候选，再按累计最多 20 MiB 原文选择；单份保留大纲的 200 符号上限。结果优先精确名称，其次限定名，最后仅路径匹配，并按路径/行号/类型/UUID 稳定排序。`matched_count` 仅表示扫描内、应用返回上限前的匹配数；`truncated=true` 表示来源、字节、单份符号或结果数量至少一类被限制，空结果不能据此推断整个项目不存在目标。调整仓库/关键词可收窄范围，但本接口不保证扫描超出 100 份的全部资料。

空白查询返回 422 `CODE_SEARCH_QUERY_EMPTY`；参数长度/类型错误返回统一 422；项目、仓库或用户越界返回 404。接口只提供已识别声明的位置，不是实体消歧或编译器全局符号索引，见 [ADR 0032](adr/0032-bounded-code-symbol-search.zh-CN.md)。

### 查询代码结构（Java 专项扩展如下）

静态导入扩展保留响应形状：`import static Type.method` / `Type.*` 的未限定调用可返回同仓库其他 ready 来源中的静态方法候选，`cross_file_calls[].receiver` 为标记字符串 `import static`（不是源码接收者表达式）。原方法 ID、路径、行号及 `resolved`/`ambiguous` 语义不变。当前/继承成员名称保守阻止导入回退，即使参数数量不符；显式导入阻止通配回退，目标缺失时不猜测。排除非静态、私有和跨包不可访问候选；限定 `this`/`super` 不使用静态导入。完整类型/访问检查仍未实现，见 [ADR 0030](adr/0030-java-static-import-calls.zh-CN.md)。

`GET /api/v1/sources/{source_id}/code-structure`

适用于状态为 `ready` 的支持代码来源。新语言返回 `language/has_syntax_errors/symbols`，关系数组为空；以下调用能力仅适用于 Java。返回最多 200 个 `type` / `field` / `method` 符号、最多 500 条同文件方法调用，并在同仓库最多 100 份已解析 Java 来源中返回有界跨文件类型关系、最多 500 个相关方法和 500 条跨文件调用；相关来源原文累计最多读取 20 MiB。未归属仓库的旧来源只在同项目的未归属集合中解析。每个符号包含稳定 `id`、名称、限定名、所属类型和包含式行号。同文件调用包含调用方、候选被调方法 ID、名称、行号及 `resolved` / `ambiguous` 状态。

`related_types` 返回关系目标的稳定类型 ID、来源 ID、相对路径优先的 `source_path`、包限定名和行号；`type_relationships` 返回当前类型符号 ID、目标 ID 列表、源码中的目标名、`extends` / `implements`、声明行及 `resolved` / `ambiguous`。`related_methods` 返回跨文件目标方法的稳定 ID、来源、路径、所属包限定类型、方法限定名和行号；`cross_file_calls` 返回当前调用方 ID、目标方法 ID 列表、接收者、方法名、调用行及解析状态。解析遵循显式导入、同包和通配导入优先级，只返回能匹配同仓库已解析来源的目标；外部库、其他仓库和未解析文件不会伪造关系。同一路径的多个不可变版本若声明相同包限定类型，也会作为多个候选显示为 `ambiguous`。`truncated=true` 表示符号、调用、相关类型/方法、类型关系、跨文件调用或仓库来源至少一类达到上限。

`POST /api/v1/sources/{source_id}/agent-call-analysis`

可选 query `strategy=single_step|tools`，默认 `single_step`，非法值返回 422。`tools` 只在已授权仓库快照上提供 `read_source_range/get_imports/search_symbols/find_references/get_type_members`，最多 4 轮模型、8 次工具、230 秒、累计工具结果 20000 字符、累计输入 240000 字符。单次读取最多 80 行；不开放任意路径、Shell、网络或数据库。首轮要求工具、末轮强制结束；失败不自动重试，初始输入超限返回 413，工具/轮次/累计上下文预算或非法输出返回 502，连接超时/供应商不可用返回 503。项目归档或越界来源返回 404。追加响应字段 `strategy`、`tool_call_count`、`tool_trace`；轨迹项仅含 `name,status,result_characters,duration_ms`，不含源码参数或模型内部推理。`provider_call_count` 是实际模型轮数。详见 [ADR 0043](adr/0043-bounded-read-only-tool-agent.zh-CN.md)。

该接口只接受已解析代码来源，无请求体。它从同仓库兼容语言族中读取最多 99 份 ready 来源和 20 MiB 原文，本地生成调用点及同名方法候选；最多把 100 个调用、每个 20 个目标候选交给配置的 DeepSeek 模型。Agent 必须为每个调用返回一条 `resolved/ambiguous/unresolved` 决定，只能选择服务器给定的目标 UUID。后端验证完整性、目标归属和数量语义，再从原文生成 `call_quote` 与 `related_symbols[].quote`。

响应包含 `source_id,language,model,prompt_version,calls,related_symbols,scanned_source_count,detected_call_count,candidate_call_count,provider_call_count,truncated,has_syntax_errors`。每条调用包含可空 `caller_id`、目标 ID、接收者、名称、行列、精确调用行、解析状态、置信度和简短依据。没有候选时 `provider_call_count=0`、`model=null`。未配置返回 503 `CALL_AGENT_NOT_CONFIGURED`；供应商失败返回 503；非法/伪造输出返回 502；输入超过配置上限返回 413。结果同步且不持久化，不表示编译器认证或运行时动态分派，也不进入正式知识图谱。边界见 [ADR 0041](adr/0041-bounded-multilanguage-agent-call-analysis.zh-CN.md)。

Java 分析 V1 保留上述接口形状与上限，不写入正式图谱。同文件调用和跨文件候选共用作用域与实参数量筛选：支持普通块/if/else/while/try/catch/finally、带花括号的增强/传统 for 与资源 try。显式类型、构造器初始化 `var`、返回类型一致且可访问的仓库内静态工厂初始化 `var`、参数/字段及头部变量按词法范围解析；未知绑定阻止字段/类型回退。工厂支持完整 `Type.factory(...)` 及未限定名 `factory(...)`，后者优先当前/继承成员，再使用显式/通配静态导入；成员名称即使参数数量不符也阻止导入回退。精确当前类型的私有静态成员可由未限定名调用；所选导入所有者缺失、成员查找截断、类型限定名被受支持变量遮蔽或方法类型参数返回时保持未知。头部调用省略，循环/资源变量不会泄漏到块外或 catch/finally。

仓库内继承候选按原声明来源查找，支持未限定/`this`/`super` 继承调用，按已知参数签名抑制覆盖、去重菱形路径；不继承私有方法、构造器或接口静态方法。单次查找最多遍历 256 个继承状态；继承环/预算触顶也使 `truncated=true`。实参数量筛选支持可变参数，不判断实参类型；同数量类型重载和重复不可变版本仍为 `ambiguous`，不确定表达式保留候选。`resolved` 仅表示该有界分析内唯一候选，不代表编译器验证或运行时目标。

数组字段/参数/局部变量与可变参数保留未知绑定，不能作为元素类接收者，也不会回退到同名字段或导入类型；支持变量名前/后及多维方括号。标量泛型参数内的数组不把外层接收者变成数组。工厂返回类型已在工厂声明文件解析，后续调用按该精确限定名匹配，包括默认包名称，不能被调用文件的同名导入改指向其他类型；重复不可变版本继续保留歧义。响应形状与来源/分块/正式图谱均不改变。

传统 for 的单声明及资源 try 的单/多声明头部，也支持用完整静态工厂初始化 `var`，复用方法体局部变量的候选、遮蔽和一致返回类型规则。按源码顺序处理头部与方法体声明，资源列表按声明顺序绑定名称；后声明的资源不能反向遮蔽前面的初始化表达式。绑定只在花括号主体及嵌套块可见，不泄漏到 catch/finally 或相邻块；未知工厂仍遮蔽，头部表达式不新增调用边。见 [ADR 0038](adr/0038-java-header-factory-receivers.zh-CN.md)。

不支持区域仍保守处理；完整 AST、外部依赖、动态分派、泛型替换、通用工厂/链式推断、重新赋值数据流和完整控制流不在 V1 范围。静态工厂切片不支持链式、强制转换、条件表达式、实例、`this`/`super` 限定或重新赋值形式，也不支持复杂/带注解/传统 for 多变量声明等既有排除头部。能力矩阵、精确限制及综合验收步骤见 [Java 分析 V1](JAVA_ANALYSIS_V1.zh-CN.md)、[ADR 0029](adr/0029-java-analysis-v1.zh-CN.md)、[ADR 0036](adr/0036-bounded-java-static-factory-var-receivers.zh-CN.md)、[ADR 0037](adr/0037-unqualified-java-factory-receivers.zh-CN.md) 与 [ADR 0038](adr/0038-java-header-factory-receivers.zh-CN.md)。

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

状态：已实现，只读。返回 `entity`、`evidence`、`relationships` 和 `truncated`。证据包含 `id`、`source_id`、`chunk_id`、`title`、`uri`、可空 `git_url`、`quote`、`start_line`、`end_line`、`heading_path`；直接关系最多返回 100 条。`uri` 始终保留应用内 `project://` 定位。GitHub 文件来源的 `git_url` 固定到 Commit 与 `#Lx-Ly` 行号；GitHub 工作项来源打开规范 Issue/PR 会话，行号只描述本地保存的 Markdown 快照。

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

状态：已实现正式实体的关键词检索、显式构建索引的向量检索，以及融合可见一跳关系的混合检索。

### 重建项目语义索引

`POST /api/v1/projects/{project_id}/embeddings/rebuild`

无请求体。后端将正式实体的类型、名称、摘要和证据摘录发送到已配置的 OpenAI-compatible 嵌入服务，保存 1024 维向量；模型与内容哈希未变化的记录复用。返回 `model`、`dimensions`、`eligible_count`、`updated_count` 和 `reused_count`。未配置服务返回 503 `EMBEDDING_NOT_CONFIGURED`，供应商失败返回 503 `EMBEDDING_PROVIDER_FAILED`。调用是显式的，不属于知识确认事务。

### 搜索知识

`GET /api/v1/projects/{project_id}/search`

查询参数：

- `q`：必填，1–200 字符。`keyword` 模式按空白切分为 1–8 个词；`hybrid` 的关键词分支最多使用前 8 个不同词，两者都要求所用词在名称、摘要或证据摘录中命中，重复词只计分一次。`vector` 与 `hybrid` 的向量分支把规范化后的完整文本作为查询。
- `mode`：`keyword`（默认）、`bm25`、`vector`、`hybrid` 或 `rrf`。新增 `bm25` 是离线中英混合词法排序，不依赖模型或向量索引；不会改变旧关键词/混合语义。
- `types`：可选，逗号分隔的实体类型。
- `valid_at`：可选带时区时间，沿用图谱的有效区间和归档过滤。
- `top_k`：1–50，默认 10。

返回 `{ "query": "规范化空白后的查询", "mode": "keyword", "items": [...], "truncated": false }`。每条 `items` 包含 `entity`、相关模式的分数字段、`matched_fields`、`graph_connections` 及最多 3 条 `evidence`。向量和混合模式还返回 `indexed_count` 与 `eligible_count`；混合模式另返回 `weights`。结果仅含正式实体，不含待审核/拒绝候选或关系。

`bm25` 使用 Han 单字/相邻二字片段、casefold Unicode 单词及标识符/部分，允许多词软匹配，不套用旧模式 8 词 AND 规则。纯标点查询返回 422 `SEARCH_QUERY_INVALID`（符号精确检索可用 `keyword`）。每项新增可空 `bm25_score`；顶层 `lexical` 包含 `protocol=mixed-bm25-v1`、`query_terms`、`scanned_count`、`entity_limit=1000`、`text_limit_per_entity=4000`、`truncated_reasons`（`entity_limit/evidence_limit/text_limit`）。仅在作用域/有效时间内的正式实体上统计；最多 5000 条排序证据、每条最多 2000 字符。语料、证据或排序文本省略也使 `truncated=true`，不能把它只解释为 Top K 截断。`eligible_count` 是可见实体总数，`indexed_count=null`，并非“语义索引未完成”。返回证据仍是精确原文，BM25 不写图谱、不调用外部服务。详见 [ADR 0044](adr/0044-bounded-offline-bm25-search.zh-CN.md)。

向量分支先本地校验嵌入配置、统计同模型/维度的可见索引，为零则直接返回空向量结果，避免空项目/空索引仍付费请求查询嵌入。混合的字面/图分支仍可返回命中。未配置、错误维度、供应商故障的错误语义保留，不静默回退；有匹配索引时仍正常调用查询嵌入。

关键词得分规则：名称与完整查询忽略大小写完全相同加 50，每个不同词在名称/摘要/证据中命中分别加 10/3/1，不按重复引用计分。向量模式使用同模型的余弦相似度，PostgreSQL 执行 pgvector 精确距离排序。混合模式各取最多 100 个关键词/向量种子，并读取最多 500 条可见一跳关系；关键词按候选池最高分归一，向量贡献截断到 `0..1`，图得分为相邻种子最强归一化信号乘关系置信度，最终为 `0.3 * keyword_component + 0.4 * vector_component + 0.3 * graph_score`。`graph_connections` 最多给出 3 条关系依据。图扩展可召回原本未被关键词/向量命中的邻居。

关键词/向量模式同分按名称、UUID 稳定排序；混合模式按最终得分、名称、UUID 排序。所有分数都不表示知识置信度。无结果返回空数组，超出 `top_k` 或图扩展上限时设置 `truncated`。

关键词匹配采用忽略大小写的字面子串；`%`、`_` 不作通配符，中文不自动分词。搜索校验用户与项目，归档/不可访问项目返回 404；关键词查询空白或超过 8 个词返回 422 `SEARCH_QUERY_INVALID`，混合查询只在空白时返回该错误，未知类型返回 422 `SEARCH_TYPES_INVALID`。关键词查询不调用模型；向量与混合查询会把查询文本发送到已配置的嵌入服务，但只读数据库。关系也必须符合用户、项目、状态和有效时间边界。见 ADR 0008、ADR 0009 与 ADR 0010。

## 证据问答

状态：已实现同步、非持久化的第一版。每次请求使用显式选定的检索方式，只允许模型依据选定的正式证据回答；当前不提供历史查询、流式输出或多轮会话。

### 创建问答请求

`POST /api/v1/projects/{project_id}/questions`

```json
{
  "question": "事件驱动架构在哪些代码中实现？",
  "valid_at": null
}
```

`question` 去除首尾空白后必须为 1–200 字符；`valid_at` 可选，提供时必须带时区。`retrieval_mode` 可选 hybrid/rrf/vector/bm25，默认 hybrid。最多选 5 个实体，按实体排名轮流取原文，每轮每实体一条，最多 12 段。使用 `(source_id,chunk_id,start_line,end_line,quote)` 去重，保留首条正式证据 ID/归属，不合并不同来源或版本。问题全文用于向量查询；关键词分支最多使用前 8 个不同空白分词。hybrid/rrf/vector 要求嵌入配置；bm25 检索不调用嵌入，但有证据时生成答案仍需 DeepSeek。retrieval 新增 mode/bm25_hits/unique_evidence_count/duplicate_evidence_count/truncated；vector_hits 统计具有向量得分的返回实体数，计数不代表答案可信度。

```json
{
  "id": "...",
  "question": "事件驱动架构在哪些代码中实现？",
  "supported": true,
  "answer": "...",
  "confidence": 0.88,
  "entity_ids": ["..."],
  "evidence": [
    {
      "id": "...",
      "entity_id": "...",
      "entity_name": "DomainEvent",
      "source_id": "...",
      "title": "DomainEvent.java",
      "uri": "project://commerce-core/domain/DomainEvent.java",
      "chunk_id": "...",
      "quote": "...",
      "start_line": 12,
      "end_line": 28,
      "heading_path": ["Domain"]
    }
  ],
  "retrieval": {
    "keyword_hits": 3,
    "vector_hits": 5,
    "graph_hits": 2,
    "indexed_count": 7,
    "eligible_count": 7
  },
  "missing_information": []
}
```

DeepSeek 收到的内容只含问题及选定证据的 ID、实体名、标题、行号和引用原文。模型输出经过严格 Schema 校验：`supported=true` 必须引用证据；`supported=false` 必须填写 `missing_information`；引用 ID 必须属于本次检索集合，最多返回 5 条引用。接口只返回实际引用的证据。

检索不到正式证据时，接口直接返回 `supported=false`、置信度 0 和补充资料建议，不调用回答模型。检索到证据但未配置 DeepSeek 时返回 503 `QUESTION_NOT_CONFIGURED`；供应商调用失败或响应无效分别返回 503 `QUESTION_PROVIDER_FAILED` / `QUESTION_OUTPUT_INVALID`；引用越界返回 502 `QUESTION_EVIDENCE_INVALID`。项目不可访问沿用 404，输入校验失败返回 422。

本接口不写入问题或答案；响应 `id` 仅用于标识当次载荷，不能用于后续查询。决策见 ADR 0011。

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
  "candidate_count": 3,
  "review_counts": { "pending": 3, "confirmed": 0, "rejected": 0 }
}
```

`task` 实际包含任务查询接口的全部字段，上例仅展示关键字段。上传产生的解析任务及项目资料列表的 `task_id` 保持不变；候选提取使用另一任务。`GET /api/v1/sources/{source_id}/extraction` 返回同一结构；尚未提取时 `task` 为 `null`、数量为 0，不会调用模型。

仅允许当前用户有效项目内已解析且有分块的资料；未解析或无分块返回 HTTP 409，未配置密钥返回 HTTP 503，输入超过默认 100 个分块/序列化 JSON 60000 字符返回 HTTP 413，不会截断资料。成功结果按来源/提示版本复用，不再调用模型。正在执行且租约有效时返回 HTTP 409 `EXTRACTION_RUNNING`；租约过期允许显式接手，旧执行写入返回 HTTP 409 `EXTRACTION_REPLACED`。解析 Worker 不消费候选任务。

模型连接/认证/余额/限流错误、无效 JSON、未完整结束的输出或伪造引用，返回 HTTP 200 和 `failed` 任务，`error.code` 为 `EXTRACTION_PROVIDER_FAILED`、`EXTRACTION_OUTPUT_INVALID` 或 `EXTRACTION_EVIDENCE_INVALID`。不保存部分候选，不改变资料已解析状态，不暴露原始模型错误或密钥。失败可手动重试；不自动重试或强制重新提取成功批次。

### 查询候选知识

`GET /api/v1/projects/{project_id}/reviews`

分页返回 `items`、`page`、`page_size`、`total`，实体候选稳定排在关系候选之前，各组再按创建时间、ID 排序。`page >= 1`、`1 <= page_size <= 100`；支持 `source_id`、`review_status`（`pending`/`confirmed`/`rejected`）、`candidate_type` 和 `min_confidence`（0–1）。不传审核状态时包含所有候选，空列表或越界页返回空 `items`。不存在、其他用户或已归档项目返回 HTTP 404；来源筛选必须属于当前项目。

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

已确认但尚未生成正式记录的旧候选，可再次提交相同确认进行补写；该重放不重复模型调用，也不新增审核事件。当前不支持 `merge`、撤销、修改类型/证据/端点；实体消歧和问答仍属于后续设计。

## 第一版接口优先级

1. 项目创建与查询。
2. Markdown/Java 上传、解析与任务状态。
3. 候选知识查询与确认。
4. 局部图谱和节点详情。
5. 证据问答。
6. 历史状态和替代关系查询。


## 可选排名融合（ADR 0045）

`GET /projects/{id}/search?mode=rrf` 在同一时间与项目/类型作用域内各取最多 100 条 BM25 和向量结果，按 `sum(1/(60+rank))` 融合，分支缺席贡献为 0；不做图关系扩展。同分按名称/UUID 稳定排序。返回 `rrf_score,lexical_rank,vector_rank`、原始分数、lexical 扫描预算、indexed_count/eligible_count 和截断标记。要求有效嵌入配置，空索引不发嵌入请求，供应商错误不静默回退。分数不是概率或可回答性阈值。搜索默认仍为 keyword，问答默认仍为 hybrid。

抽取 POST 与状态 GET 的 `review_counts` 是同用户/项目/来源/抽取任务下整份候选的实时统计，不受候选列表分页影响；重复抽取不重新调用模型，但统计可随审核变化。


## 显式批量审核与索引状态（ADR 0046）

`POST /api/v1/projects/{project_id}/reviews/resolve-batch`：

```json
{ "source_id": "UUID", "review_ids": ["UUID"], "action": "confirm" }
```

`action` 为 confirm/reject；1–100 个 review_ids 必须不重复且全部属于当前用户的有效项目和指定资料。整批预校验后持有项目锁，先实体后关系，复用原审核/审计/提升服务，只提交一次；任一项失败整批回滚。关系端点仍须已确认或在此次选择中先确认，不隐式增加选择。同动作重试幂等。返回 `{items: ReviewRead[], processed_count: number}`，items 保持请求 ID 顺序；processed_count 表示处理的请求项数，也包含幂等项。无修改名称/摘要字段；需修改时仍使用单项接口。作用域不符返回 404 REVIEW_NOT_FOUND，依赖/已处理冲突沿用原 409；输入无效返回 422。

`GET /api/v1/projects/{project_id}/embeddings/status?valid_at=...`：只读且不调用供应商。valid_at 可选且必须带时区，沿用项目图谱的当前/历史可见性，不受搜索类型筛选影响。返回 model/dimensions/configured/checked_at、eligible_count/indexed_count/missing_count，以及 stale_count/current_count/scanned_count/scan_limit/truncated。前三种数量覆盖整个用户/项目/时间范围，内容哈希的 stale/current 只覆盖最多 1000 个实际检查实体；truncated 时不能据零 stale 推断全部新鲜。模型或维度不匹配视为缺失。configured 只表示本地配置校验通过，不表示服务连通，也不暴露密钥。按与重建相同顺序计算规范实体文本哈希，无写入，无嵌入请求。


## 候选筛选、治理类别与证据归属（ADR 0047）

`GET /projects/{id}/reviews` 新增可选 kind=entity|relation 和 q（最多 200 字符）。q 规范化空白后对名称/摘要作字面、不区分大小写的子串查询，百分号/下划线不是通配符；与 source_id/review_status/candidate_type/min_confidence 共同作用于 total 与分页之前。不传新参数保持旧结果。整份来源 review_counts 不受列表筛选影响。未知 kind 或超长 q 返回 422，越权/错误来源仍为 404。

`GET /projects/{id}/governance?kind=duplicate` 的 kind 可为 missing_evidence/duplicate/possible_conflict/orphan。不传仍返回全部。先在既有最多 1000 当前实体的扫描范围内生成建议与 counts_by_kind，再按 kind 筛选并应用 limit；返回 kind_filter（可空）。counts_by_kind 不受所选类别或结果 limit 影响，但只代表有界扫描结果。truncated 仍表示扫描或当前类别结果被截断。

问答 evidence 新增 related_entities: [{id,name}]，记录引用同一已选原文位置的检索实体，不新增规范引用 ID。主要 entity_id/entity_name 与响应 entity_ids 保留原归属语义；提供给模型的片段增加 entity_names 名称列表。引用归属校验、证据预算、来源/版本隔离及回答输出约束不变。

双实体核对复用 GET /knowledge/entities/{id}，不新增写入 API。前端必须校验两份响应均为所请求 ID 且属于当前项目；任意失败时不展示部分结果。

## 关系审核依赖快照（ADR 0048）

`GET /api/v1/projects/{project_id}/reviews` 的每个关系候选新增 `endpoints: [{id,name,review_status}]`，按起点/终点顺序去重，最多两项。只返回同用户/项目/资料/成功抽取任务且 kind=entity 的可访问端点；缺失或不兼容端点省略，不回退查找其他任务/资料。端点读取独立于外层列表筛选和分页，total 仍仅统计列表候选；最多一次附加查询，读取 ID 数量不超过两倍 page_size。实体候选与单项/批量审核响应的 endpoints 默认空列表；需刷新列表获得快照。

快照可能过期，不能作为绕过最终审核校验的依据。单项确认仍要求两端已确认；批量依赖只接受明确所选实体先确认，任一冲突仍整批回滚。未新增写入接口、自动选择、审核撤销、数据库迁移或模型调用。
