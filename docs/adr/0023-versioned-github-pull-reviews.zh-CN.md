# ADR 0023：独立版本化有界 GitHub Pull Request Review 活动


- Status: Accepted
- Date: 2026-10-21

## 背景

既有显式 GitHub 活动导入按 provider item ID、`updated_at` 与评论配置版本化 Issue/Pull Request Markdown。Pull Request Review 与行级 Review Comment 是独立的 GitHub 资源，其内容变化不一定可靠地反映到 Pull Request `updated_at`；如果直接并入工作项版本键，可能错误复用过期的 Review 文本。

## 决策

对每个启用 `include_reviews=true` 的入选 Pull Request，从 REST 第一页最多读取 20 条 Pull Request Review 和 20 条行级 Review Comment，并用响应 `Link` 头报告任一集合是否还有下一页。保存 Review 状态、作者、提交时间、正文、Commit 与 URL；保存行级评论的路径/行号、作者、时间、正文、URL，以及可用时的 `in_reply_to_id`。

把这些活动渲染成与基础 Pull Request 来源分开的确定性 Markdown，并对完整渲染字节计算 SHA-256。`github_pull_review_versions` 按仓库、provider Pull Request ID 与活动摘要映射不可变来源和解析任务。重复导入相同活动时复用来源/任务；任何会改变渲染内容的 Review 变化都会生成新快照，即使基础 Pull Request 版本未变。空活动同样形成版本，以便后续活动移除仍可观察。

Review 来源使用规范 Pull Request URL 进行外部导航，并进入既有 Markdown 解析、证据、审核与提升流程。导入仍只能由用户显式触发，不会增加后台 GitHub 请求。

## 后果

- 工作项版本兼容性保持不变；迁移 `20261021_0012` 只新增一张可独立回滚的表。
- 一个入选 Pull Request 可以生成两份来源版本：基础会话和 Review 活动。
- 每次显式启用 Review 的导入都要读取有界 Review 接口，因此即使基础 Pull Request 来源复用，也能发现 Review 编辑。
- `in_reply_to_id` 保留回复链接，但 REST 快照不声称拥有完整线程分组或 resolved/unresolved 状态。
- Review 事件、附件、reaction、后续分页、Webhook、轮询与破坏性失效传播仍不在范围内。

## 备选方案

- 把 Review 字段加入工作项唯一键：不采用，因为修改既有键会增加回滚复杂度，并把 Review 变化耦合到基础会话版本。
- 依赖 Pull Request `updated_at`：不采用，因为它不能可靠标识独立 Review 资源变化。
- 现在改用 GraphQL Review Threads：推迟到确实需要完整线程与解决状态语义时再实现。
