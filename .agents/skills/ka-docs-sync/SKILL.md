---
name: ka-docs-sync
description: Knowledge Atlas 的双语文档同步。修改 API、知识模型、架构决策、能力状态或迁移版本后，需要更新 README、docs、ADR、CHANGELOG 时使用。触发词：docs, README, ADR, CHANGELOG, translation, 文档, 翻译, 变更记录.
---

# 文档同步

仓库文档是交付物的一部分。规则是：**行为变了，对应文档同轮更新；有中文版的，两种语言一起改。**

## 何时使用

- 修改 API 形状、数据模型、迁移版本、能力状态。
- 新增或变更架构决策。
- 准备提交、发版、写验收记录。
- 发现文档与代码不一致。

## 更新矩阵

| 改动 | 必须更新 |
| --- | --- |
| API 路径、字段、错误码、分页 | `docs/API_CONTRACT.md`；`backend/README.md` 与中文版 |
| 实体、关系、证据、时序语义 | `docs/KNOWLEDGE_MODEL.md`；必要时 ADR |
| 架构边界、存储选型、任务模型 | `docs/adr/` 新 ADR，并更新 ADR 索引 |
| 能力状态、安装方式、仓库结构 | `README.md`；`PLANS.md`、`docs/ROADMAP.md` |
| 前端结构、交互、组件职责 | `docs/FRONTEND.md` |
| 环境、命令、端口、配置项 | `docs/DEVELOPMENT_SETUP.md` 与中文版；`backend/README.md` |
| 每次行为变化 | `CHANGELOG.md` 的 `Unreleased` |
| 安全、贡献流程 | `SECURITY.md`、`CONTRIBUTING.md` |

## 双语配对

以下文件成对维护，语言链接必须双向有效：

- `AGENTS.md` ↔ `AGENTS.zh-CN.md`
- `PLANS.md` ↔ `PLANS.zh-CN.md`
- `CHANGELOG.md` ↔ `CHANGELOG.zh-CN.md`
- `CONTRIBUTING.md` ↔ `CONTRIBUTING.zh-CN.md`
- `SECURITY.md` ↔ `SECURITY.zh-CN.md`
- `docs/DEVELOPMENT_SETUP.md` ↔ `docs/DEVELOPMENT_SETUP.zh-CN.md`
- `backend/README.md` ↔ `backend/README.zh-CN.md`
- `docs/adr/README.md` ↔ `docs/adr/README.zh-CN.md`
- 每个 `docs/adr/NNNN-*.md` ↔ `NNNN-*.zh-CN.md`

约定：

- 两种语言保留相同的命令、标识符、版本号、文件名和状态。
- 不机翻专有名词；`SUPERSEDES`、`valid_from`、`pending` 等保持原样。
- 语言切换链接指向对方文件顶部。
- 只改一种语言时，在提交说明里明确“翻译待补”，不要假装已同步。

## 状态标注

- 已实现：写清当前行为、限制和验收状态。
- 规划中：明确写“规划中/尚未实现”，不得描述成已有能力。
- Mock：必须标注“演示数据”，不能与真实接口混写。
- 待验收：区分“单元测试通过”和“真实服务/真实模型通过”。

## ADR 流程

- 触发：存储选型、任务执行模型、抽取/审核边界、正式图谱写入等架构级决策。
- 命名：`docs/adr/NNNN-kebab-title.md`，同时写 `.zh-CN.md`。
- 内容：Status、Date、Decision、Consequences；写清边界和未做的事。
- 更新 `docs/adr/README.md` 索引，保持中英同步。
- 决策改变时新增 ADR 标明取代关系，不直接改写旧 ADR 的结论。

## CHANGELOG

- 变化写在 `## Unreleased` 下，按 `Added` / `Changed` / `Known limitations` 分组。
- 只写用户可感知的行为，不写“重构了某文件”。
- 已知限制要具体：哪些验证没做、哪些能力仍是 Mock。
- 中英两版同轮更新。

## 漂移检查

提交前用几分钟核对：

- 迁移 head：`alembic heads` 与文档里的“预期版本”是否一致。
- 能力列表：README 的“当前状态”是否仍与代码一致。
- 图谱/检索/问答：是否仍被错误描述为已实现或未实现。
- 搜索关键词：`尚未实现`、`规划中`、`Mock`、`待验收`，逐个确认。
- 链接：双语互链、ADR 索引、README 文档索引是否可点。
- 错误结构、分页参数、状态枚举是否在 API 文档中更新。

本轮已同步的典型漂移（保留为检查示例）：

- 正式图谱落地后，`README.md`、`docs/ARCHITECTURE.md`、`docs/ROADMAP.md`、`backend/README.md` 曾仍写“尚未实现”。
- 迁移 head 变为 `0005` 后，`docs/DEVELOPMENT_SETUP.zh-CN.md` 与后端 README 曾仍写预期 `0004`。
- ADR 0007 落地后，`docs/adr/README.md` 的既有决策索引曾缺少条目。
- `CHANGELOG` 曾缺少图谱写入记录。

这些现在已修正；下次改行为时按上面的检查项重新核对。

## 完成检查

- [ ] 行为、文档、测试三者描述一致。
- [ ] 双语文件同轮更新，语言链接有效。
- [ ] 规划中/已实现/Mock/待验收标注准确。
- [ ] CHANGELOG 已更新。
- [ ] ADR 索引与新增决策一致。
- [ ] 文档中的命令实际可执行（或明确标注前提）。

## 2026-10-26 功能补全更新

2026-10-26 功能状态以 FUNCTIONAL_COMPLETION_20261026 双语报告与 ADR 0056–0059 为准；旧日期检查点保留历史数字。区分已实现、临时 schema 功能验证、真实公开模型实验、私有授权待验收及人工覆盖率 0%。

## 2026-10-29 当前优化边界

Current root README/PLANS/ROADMAP/FRONTEND consolidate capabilities; pre-20261029 snapshots live under docs/archive/pre-optimization-20261029 with corrected relative links. Preserve dated experiment/acceptance numbers. Update ADR0060–0063, exact API context/error shape, schema readiness, holdout separation and benchmark scope in paired language docs. Do not convert deferred human grading into achieved quality. Report current database0018 separately from older historical checkpoints.

## Single-project multi-agent extension (ADR0064–0065)

Current extension is ADR0064–0065, docs/MULTI_AGENT.md and .zh-CN.md, with agent_runs migration0019. Update actual canonical tree and legacy aliases, shared/per-role attempted-call limits, explicit human resume, synchronous event persistence and lack of crash-node recovery. Keep root/backend/setup/API/frontend/knowledge-model/plan/changelog paired where companions exist. Preserve historical0018 reports and frozen experiments. Do not describe stub protocol tests as new real-provider quality or completed human grading.

## Batched lexical v2 (ADR 0066)

Current BM25/source-aware BM25 and the RRF lexical leg use v2 identifiers, 200-entity keyset batches, a 50k scan ceiling, global corpus statistics, 32 ranking quotes per canonical entity and the existing text limits. Document matched_count/results_truncated separately from omitted scan/text. Update API/current plans/backend README and bilingual ADR/changelog together; keep v1 experiment assets and historical performance/quality reports unchanged. Synchronous batching does not establish cross-request resume, repeatable-read isolation or measured v2 production capacity.

## Durable agent progress (ADR 0067)

Current agent events and call reservations persist during synchronous execution; validated code/answer and committed extraction IDs have checkpoints. Replace current end-only persistence descriptions, preserve historical acceptance reports, and describe primary status vs partial result, pending-write refusal, lease fencing, conservative reservations and lack of automatic paid continuation. Schema/head remains0019. Sync API, MULTI_AGENT, architecture, frontend labels, backend READMEs, plans, changelog and paired ADR; stub integration is not provider quality.
