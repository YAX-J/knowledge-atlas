# ADR 0031：以类型安全的来源复用恢复不完整 GitHub 快照

[English](0031-recoverable-typed-github-snapshots.md)

- 状态：已接受
- 日期：2026-10-22
- 补充：ADR 0019 的缓存条件与复用身份。

## 背景

无条件同 Commit 短路，使截断或大小受限快照无法通过已有同步操作补齐。仅按 blob 复用还会让 Markdown/Java 后缀变化继承错误来源和解析任务。截断文件集合也不能证明旧路径已经消失。

## 决策

- 重复 ref/Commit 仅在最新快照未截断、删除检测完整且所有成功文件引用仍兼容时短路。确定性空文件/编码/路径跳过可缓存；大小超限跳过保留可重试性。
- 否则下一次显式同步重读有界 tree、复用成功文件并重试缺失/跳过项，即使 Commit 相同也保存新的不可变快照。仍维持每次最多选择 50 份文件、下载 20 MiB。不增加自动重试或分页；固定选择上限仍可能阻止完整导入。
- 可复用来源按 blob SHA 与来源类型匹配。关联快照/来源/任务，校验用户/项目/仓库归属、任务来源关联及解析器类型。保留兼容旧 Markdown 解析任务。不自动重跑普通失败解析任务。
- Markdown/Java 后缀变化创建或复用正确类型的来源/任务，不重命名不兼容来源。同类型 `.md`/`.markdown` 移动仍可复用。缓存引用缺失或不兼容时触发恢复，不改写历史快照记录。
- 只有完整 tree/文件集合可以确认重命名；不完整集合可以复用内容，但不能以猜测重命名修改来源展示路径。保留既有保守删除规则与非破坏性证据历史。
- 保持 API 形状、前端操作、数据库结构与审核知识边界。此改动不要求真实供应商调用、轮询/Webhook、破坏性修复或编译器集成。

## 影响

用户可使用既有同步操作恢复字节受限导入，或在调整限制后重试；完整快照仍保留低成本短路。恢复避免同类型来源重复及解析器错配。旧快照与证据保持可用；本功能不修复历史已解析内容，也不代表真实 GitHub/PostgreSQL 验收。

## 验证

沿用用户已选择的 Agent 执行方。使用既有后端虚拟环境、隔离 SQLite 与 HTTP 夹具，无需 GitHub/LLM 令牌或迁移。

```powershell
# backend/
.\.venv\Scripts\python.exe -m pytest tests/test_github_sync_recovery.py tests/test_github_import.py tests/test_sources.py tests/test_parsing.py tests/test_source_list.py
.\.venv\Scripts\python.exe -m pytest
# repository root
git diff --check
```

预期：恢复保留成功 ID/历史，完整快照不请求 tree/blob，跨类型变化使用正确解析器，拒绝越界/失效引用，不完整集合不推断重命名/删除。原生 PostgreSQL、真实 GitHub 和浏览器验收仍是独立工作。

2026-10-22 由 Agent 执行：51 项聚焦测试（含 19 项恢复用例）、294 项完整后端测试全部通过，保留一条既有 Starlette 弃用警告。沿用用户选择的执行方，在 Windows 沙箱外使用隔离 SQLite 与模拟 HTTP 响应；未进行真实 GitHub/LLM、原生 PostgreSQL 或浏览器验收。
