# ADR 0024：通过 GraphQL 快照化有界 GitHub Review thread 状态


- Status: Accepted
- Date: 2026-10-21

## 背景

ADR 0023 通过 REST 导入 Pull Request Review 与行级 Review Comment，并保留 `in_reply_to_id`，但 REST 不提供完整线程分组或当前解决状态。GitHub GraphQL 的 Pull Request `reviewThreads` 可返回当前解决状态、解决者、位置、过期状态与评论成员关系。GitHub 会通过后续 webhook 提供 resolved/unresolved 动作事件，但查询接口不提供权威的历史事件时间。

## 决策

当 `include_reviews=true` 且 `include_review_threads=true` 时，为每个入选 Pull Request 的 Review 快照补充 GraphQL 返回的前 20 个 Review thread，以及每个 thread 前 20 个评论标识。把稳定 thread ID、当前 resolved/unresolved 状态、可用的解决者、路径与行号范围、主题、过期状态和有界评论成员关系渲染到同一份确定性 Review Markdown。状态变化会改变活动摘要并创建新的不可变 Review 快照，无需依赖基础 Pull Request 的 `updated_at`。

GitHub GraphQL 必须认证。后端未配置 `GITHUB_TOKEN` 时，既有 REST Review 导入继续成功，在快照中渲染明确的令牌缺失标记，并返回 `review_threads_status=token_required`；不得把未读取误称为空线程。已经请求的 GraphQL 调用若失败或响应结构无效，则沿用脱敏后的 GitHub 供应商错误。

在 `github_pull_review_versions` 持久化 thread 数量、已解决数量、是否纳入及截断元数据。`review_threads_truncated` 同时涵盖 thread 或评论成员关系存在后续页。导入保持显式且有界。

## 后果

- 连续导入可以表明 thread 状态在两个快照之间发生变化，但不能声称得到精确解决事件时间。
- 迁移 `20261021_0013` 增加可回滚的元数据列，并以零值/未纳入默认值保留已有 Review 版本。
- 无令牌时仍可导入公开 REST 数据；完整 thread 状态补充需要具备读取权限的令牌和已配置 GraphQL 端点。
- 权威 resolved/unresolved 事件历史、Webhook 投递、附件、reaction、完整分页、轮询与破坏性失效传播仍不在范围内。

## 备选方案

- 从 REST 回复关系推断解决状态：不采用，因为回复结构不能证明解决状态，也不能标识解决者。
- 把快照差异表述为精确事件：不采用，因为查询快照不提供权威动作时间。
- 所有 Review 导入都强制使用 GraphQL：不采用，因为会让无需认证的公开 REST 导入退化。
