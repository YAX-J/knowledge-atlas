# 发现与审核流程验收 — 2026-10-25

[English](DISCOVERY_OPTIMIZATION_20261025.md)

本轮按 [ADR 0047](adr/0047-filtered-discovery-evidence-attribution.zh-CN.md) 实现：

- 候选审核支持服务端组合筛选状态、实体/关系类型和名称/摘要字面关键词，先筛选再分页。整份资料的审核进度独立于筛选结果；切换条件会清除隐藏选择并隔离过期响应。
- 知识治理先筛选问题类别再应用返回上限，并报告有界扫描内的分类数量。涉及两个实体的问题可打开只读对照，分别展示原文证据，支持加载、失败重试和上下文校验。
- 问答中的同一段原文只显示一次，同时保留所有已检索关联实体，供导航和模型上下文使用。主归属实体 ID 与规范引用校验保持原语义，持久化证据不会合并。

## 验证

用户已授权 Agent 执行后端聚焦与全量测试、原生 PostgreSQL 验收、前端测试与构建、桌面浏览器走查和 `git diff --check`，不调用真实模型。

| 检查 | 实际结果 |
| --- | --- |
| 发现流程聚焦测试 | `tests/test_knowledge_discovery.py`：4 项通过 |
| 后端全量 | `python -m pytest --cov=app --cov-fail-under=90 --cov-report=term --cov-report=xml:../output/backend-coverage.xml --tb=short --show-capture=no`：632 项通过、5 项跳过，覆盖率 94.48% |
| 原生数据库 | `python -m scripts.verify_native`：PostgreSQL 17.10 / pgvector 0.8.7 验收通过，包含发现流程回归；临时 schema 已清理，应用迁移标记未改变 |
| 前端测试 | `npm run test:coverage`：7 个文件、37 项测试通过 |
| 前端构建 | `npm run build`：类型检查和生产构建通过 |
| 桌面浏览器 | 系统 Chrome，1440 × 1100：组合筛选、空结果、整份资料进度、原文并排对照、读取失败重试，以及问答原文去重与关联实体导航通过 |
| 无障碍 | 对审核筛选、对照与问答区域运行 axe，均为 0 项违规、0 项待人工判断；对照能接收焦点，未观察到横向溢出和浏览器错误 |
| 仓库检查 | `git diff --check` 通过；修改文档的本地链接有效；未包含生成物、依赖目录、`.env` 文件或检测到的凭据模式 |

前端覆盖率沿用现有 Vitest 配置的统计范围：语句 55.5%、分支 57.35%，不能视为全应用覆盖率。后端仍有既有的 Starlette/httpx 弃用提示。

浏览器夹具使用专用 PostgreSQL schema。写入前验证了 16 张表实际归属私有 schema，并确认 `public` 中没有该测试项目。走查后已关闭命名浏览器会话、专用 API/Vite 进程并删除 schema。截图与临时脚本保留在被忽略的 `output/discovery-20261025/` 中。

## 边界

模型和嵌入输出均为本地模拟，本轮验证流程行为，不评价真实模型的回答质量、费用或延迟。未执行 GitHub 同步或付费供应商调用。治理分类数量仅覆盖有界扫描；本轮没有实现实体合并或审核撤销。不需要数据库迁移或新增依赖。
