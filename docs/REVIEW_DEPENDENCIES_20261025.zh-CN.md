# 关系审核依赖优化 — 2026-10-25


按 [ADR 0048](adr/0048-review-endpoint-visibility.zh-CN.md)，关系候选现展示两端实体的名称和审核状态，即使实体被筛除或位于其他页。单项确认要求两端已确认；批量确认也接受用户明确选中的本页待审核实体，未满足依赖会在最终提交前具名提示。拒绝仍可操作。实体列表入口重置筛选、清空隐藏选择，并聚焦审核标题。

后端以一次有界查询补充列表，每条关系最多读取两个端点 ID，严格校验用户/项目/资料/成功抽取任务/实体类别。元数据是读取时快照，原审核锁、依赖/证据校验、原子回滚和提升规则不变。无需迁移、依赖或模型调用。

## 验证

沿用用户已选择 Agent 执行的授权，实际运行：

| 检查 | 结果 |
| --- | --- |
| 后端聚焦 | `python -m pytest tests/test_knowledge_discovery.py tests/test_batch_reviews.py tests/test_knowledge.py --tb=short --show-capture=no`：36 项通过 |
| 后端全量 | `python -m pytest --cov=app --cov-fail-under=90 --cov-report=term --cov-report=xml:../output/backend-coverage.xml --tb=short --show-capture=no`：638 项通过、5 项跳过，覆盖率 94.49% |
| 原生 PostgreSQL | `python -m scripts.verify_native`：PostgreSQL 17.10 / pgvector 0.8.7 验收通过，包含资料/任务/类别隔离用例；schema 已清理，应用迁移标记未改变 |
| 前端聚焦 | `npm test -- tests/review.test.ts tests/appRequests.test.ts`：19 项通过 |
| 前端全量 | `npm run test:coverage`：8 个文件、57 项通过；限定范围语句覆盖率 63.56%、分支覆盖率 60.54% |
| 生产构建 | `npm run build`：通过 |
| 桌面浏览器 | Chrome 1440 × 1100：仅关系筛选显示两个待确认端点，单项/最终整批确认禁用；实体导航清空选择/预览并聚焦审核标题；显式确认两个实体后关系解锁，并成功确认；整份资料最终为待审核 0 / 已确认 3 |
| 无障碍 | 审核区域 axe：0 项违规、0 项待确认；无横向溢出或浏览器错误，关系确认后焦点位于对应标题 |

后端保留一条既有 Starlette/httpx 弃用提示；前端覆盖率仅描述配置范围，不等于全站覆盖。提交前检查 `git diff --check`、修改文档链接及跟踪文件卫生。

浏览器夹具使用独立原生 PostgreSQL schema，写入前验证表的实际归属，且 `public` 中没有测试项目。结束后关闭命名浏览器、记录的 API/Vite 进程并清理 schema。截图、脚本和日志保留在被忽略的 `output/review-dependencies-20261025/` 中。

所有供应商输出均为本地模拟，未调用真实模型/嵌入服务或 GitHub。本轮验证依赖处理，不评价抽取质量。列表读取后状态可能变化，后端冲突响应仍需刷新候选。不包含自动选择、实体合并或审核撤销。
