# 优化 1–3 验收 — 2026-10-25

[English](RELIABILITY_RETRIEVAL_RECOVERY_20261025.md)

已按要求顺序实现：

1. 持久化索引更新归属/状态与显式中断恢复，区分读取不可用和写入结果未知，并补齐模型等待预算。[ADR 0050](adr/0050-durable-index-rebuilds.zh-CN.md)。
2. 可选来源位置词法检索/问答、9 个新增独立功能案例，以及旧 40 题开发集的单独重放。[ADR 0051](adr/0051-source-aware-lexical-retrieval.zh-CN.md)。
3. 原生一致快照备份、归档/结构/内容校验及全新目标受控恢复。[ADR 0052](adr/0052-verified-native-backups.zh-CN.md)、[操作指南](BACKUP_RESTORE.zh-CN.md)。

## 实际验证

用户已选择 Agent 执行，本轮无真实模型/嵌入或 GitHub 调用。

| 检查 | 实际结果 |
| --- | --- |
| 后端聚焦 | `python -m pytest tests/test_embedding_jobs.py tests/test_source_retrieval.py tests/test_database_backup.py tests/test_migrations.py tests/test_run_evaluation.py --tb=short --show-capture=no`：40 项通过 |
| 后端全量 | `python -m pytest --cov=app --cov-fail-under=90 --cov-report=term --cov-report=xml:../output/backend-coverage.xml --tb=short --show-capture=no`：662 项通过、6 项跳过，语句覆盖率 94.58% |
| 原生数据库 | `python -m scripts.verify_native`：PostgreSQL 17.10 / pgvector 0.8.7 升降级/重升及独立会话并发更新拦截、状态读取通过，含新检索案例；临时 schema 清理，隔离套件未改变应用迁移标记 |
| 前端聚焦 | `npm test -- tests/knowledgeSearchState.test.ts tests/workspaces.test.ts tests/client.test.ts tests/appRequests.test.ts`：最终等待预算回归加入前为 47 项通过 |
| 最终前端 | `npm run test:coverage`：8 个文件、69 项通过；配置范围语句覆盖率 65.56%、分支 63.87%；`npm run build` 通过 |
| 备份保护 | 最终 CLI 调整后 `python -m pytest tests/test_database_backup.py`：5 项通过 |
| 真实备份/恢复 | 原生快照备份和隔离 schema 恢复先通过 17 张表，迁移后又通过全部 18 张表；行/内容/精确类型/约束/索引/扩展指纹一致，目标全部清理 |
| 应用迁移 | 完成迁移前备份及原生隔离验收后，`alembic upgrade head` 应用 `20261025_0016`；既有业务表数据指纹不变 |
| 桌面浏览器 | Chrome 1440 × 1100：中断任务须明确重试；本地模拟嵌入延迟期间刷新页面仍恢复运行状态并禁用重复更新；查询状态显示完成；成功响应丢失时提示结果未知并查询状态，只发送一次 POST；bm25_source 按文件名命中 4 条已审核知识，显示来源位置依据 |
| 无障碍 | 搜索区域 axe：0 项违规 / 0 项待确认；未观察到横向溢出或浏览器错误 |
| 仓库 | 提交前检查 `git diff --check`、本地文档链接、暂存补丁和生成物/凭据文件卫生 |

保留既有 Starlette/httpx 弃用提示；前端覆盖率是配置范围，不等于全应用。命名浏览器、记录的 QA 服务和私有夹具 schema 已清理，public 没有测试项目。临时产物及私有数据库备份保留在被忽略的 `output/reliability-123-20261025/` 中，最终可用备份为 `final-backup-0016/`。

## 检索结果

两种模式使用相同冻结语料/知识/索引指纹，供应商请求为 0。原 BM25 Recall@1/3/5 为 **60.74% / 68.24% / 74.49%**，来源位置模式为 **60.05% / 69.17% / 74.49%**。整体 Recall@5 未提高，因此仅作为位置查询可选入口，未改变默认值。完整产物见[新诊断](../evaluation/results/2026-10-25-source-mode/README.zh-CN.md)。

9 个新功能案例在开发期间编写，采用隔离合成夹具，不是保留测试集或代表性质量测量；词面误导拒答使用模拟供应商响应，验证应用契约，不评价真实模型判断。真实回答质量、一般多跳/代码推理仍无人工评分。

## 恢复边界

当前角色可 CREATE SCHEMA，但没有 CREATEDB。完整新库恢复尝试被 PostgreSQL 拒绝，未修改权限；实际以新 schema 验证恢复，包含显式外键重映射、禁止指向 public 应用表的外键、复制期间实时外键校验及完整应用表指纹。这不算完成新数据库或整个集群灾难恢复验收。

角色/服务器配置/凭据不在备份范围，仅支持可信本机归档/清单。更新仍为同步接口，服务端保存最近一次操作，不是后台任务队列或完整历史；问答/调用分析仍不持久化。明确接手中断任务可能产生额外供应商费用，不承诺计费严格一次或服务端取消。
