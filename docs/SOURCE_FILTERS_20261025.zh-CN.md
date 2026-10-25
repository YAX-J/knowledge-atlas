# 资料筛选验收 — 2026-10-25

[English](SOURCE_FILTERS_20261025.md)

[ADR 0049](adr/0049-source-discovery-filters.zh-CN.md) 新增文件名/相对路径、语言与资料解析状态组合筛选，先筛选再分页。保留默认结果、用户/项目/归档边界、任务引用和来源溯源。界面在筛选时保留已打开原文，区分无匹配与空项目，应用筛选后聚焦列表标题，切换项目重置条件；分页失败重试实际目标页，页码消失时回最后有效页。没有新增迁移或依赖。

## 验证

沿用用户已选择 Agent 执行的授权，实际运行：

| 检查 | 结果 |
| --- | --- |
| 后端聚焦 | `python -m pytest tests/test_source_filters.py tests/test_sources.py --tb=short --show-capture=no`：17 项通过 |
| 后端全量 | `python -m pytest --cov=app --cov-fail-under=90 --cov-report=term --cov-report=xml:../output/backend-coverage.xml --tb=short --show-capture=no`：643 项通过、5 项跳过，覆盖率 94.50% |
| 原生数据库 | `python -m scripts.verify_native`：PostgreSQL 17.10 / pgvector 0.8.7 验收通过，包含资料筛选套件；临时 schema 已清理，应用迁移标记未改变 |
| 前端聚焦 | `npm test -- tests/workspaces.test.ts tests/appRequests.test.ts tests/client.test.ts`：32 项通过 |
| 前端全量 | `npm run test:coverage`：8 个文件、65 项通过；配置范围语句覆盖率 64.43%、分支覆盖率 63.73% |
| 构建 | `npm run build`：严格 TypeScript 与生产构建通过 |
| 桌面浏览器 | 系统 Chrome 1440 × 1100，真实本机 API 和 26 份资料的原生 PostgreSQL 夹具：`src/storage_100%` + Python + 待解析命中一份；切到已解析得到零结果且保留已打开 Python 原文；重置恢复两页；模拟一次浏览器本地第二页错误后，重试准确到第 2 页、显示 6 项并保留同一选中资料 |
| 无障碍 | 资料筛选 axe：0 项违规、0 项待确认；标题焦点正确，无横向溢出或浏览器错误 |

提交前检查 `git diff --check`、修改文档链接和跟踪文件卫生。前端覆盖率仅描述配置文件范围，不等于全应用；后端保留既有 Starlette/httpx 弃用提示。

浏览器夹具写入前确认临时 schema 实际拥有全部业务表，生成项目不在 `public`。命名浏览器、记录的 API/Vite 进程和已验证名称的 schema 均已清理。临时截图、脚本和日志保留在被忽略的 `output/source-filters-20261025/` 中。

未调用真实模型/嵌入服务或 GitHub。筛选针对文件名/路径和资料记录状态，不涉及全文内容或任务状态历史；不会自动解析、抽取、审核或改变正式知识。
