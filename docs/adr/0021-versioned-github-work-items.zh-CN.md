# ADR 0021：把有界 GitHub 工作项导入为不可变来源版本

[English](0021-versioned-github-work-items.md)

- 状态：已接受
- 日期：2026-10-21

## 决策

Knowledge Atlas 只通过显式仓库操作导入 GitHub Issue 与 Pull Request。一次请求最多读取最近更新的 20 个工作项；启用评论时，每项最多读取 20 条 Issue 评论。Pull Request 还保存可获得的 head、base 与 merged 元数据。导入内容被确定性渲染成 Markdown，并进入既有仓库范围的 Markdown 解析与证据流程。

每个 provider item ID、GitHub `updated_at` 与评论导入配置组合标识一个不可变导入版本。重复导入同一版本/配置时复用其来源和解析任务；后续 `updated_at` 或评论配置变化时创建新的版本记录，不覆盖旧证据。`github_work_item_versions` 保存供应商身份、规范会话 URL、状态、标题、是否包含评论、已导入评论数、截断标记、来源和任务。

GitHub 工作项证据打开规范的 Issue 或 Pull Request 会话。保存的来源行号指向导入的 Markdown 快照；与仓库文件不同，GitHub 不为会话正文与评论提供不可变的行号片段 URL。

## 影响

- 远端编辑不会静默替换已用于候选知识或正式证据的文本。
- Issue/PR 内容复用既有解析器、Worker、审核、图谱、检索与问答链路。
- 导入保持有界、显式、项目隔离，令牌仍只位于后端。
- 工作项来源在本地不可变，但其规范 GitHub 会话 URL 可变化，不能单独证明历史文本。
- 本切片不包含 Review comment、Review thread、事件、附件、reaction、自动轮询、Webhook、删除传播与完整分页。
