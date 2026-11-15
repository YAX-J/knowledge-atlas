---
name: ka-docs-sync
description: Knowledge Atlas 的文档同步。修改 API、知识模型、架构决策、能力状态或迁移版本后，需要更新 README、docs、ADR、CHANGELOG 时使用。触发词：docs, README, ADR, CHANGELOG, 文档, 变更记录.
---

M3/M4 ADR0078–0079 and PROJECT_ASSISTANT_M34 have paired translations. Keep source/business head0023, immutable note references vs formal evidence, v1/v2 compatibility, capability approval defaults,8/16 shared attempts, explicit continuation, backup recovery and M5 deferred status aligned. No live-quality claim from substitute/browser tests; keep frozen evaluations/ledgers/human0 unchanged.



Current M2 contract/status lives in PROJECT_ASSISTANT_M2 pair and ADR0077. Source/business head0021 follows verified backups/restores; old M1 acceptance is historical. Sync runner startup/native and optional Compose, API202/v1 compatibility, queued/cancelled states, attempts/checkpoints/artifacts/control receipts, cumulative budgets, unknown-duration limitations and M3–M5 deferral. No input/approval/notes/write APIs or live quality are delivered.
# 文档同步

M5 offline preparation is ADR0080 plus paired PROJECT_ASSISTANT_M5 guides and an independent project-agent-m5-v1 development packet. Keep its seal/20 cases/5x4 categories/11 materials/18 checks and preflight caps160 model/320 tool/0 embedding/0 judge aligned. Distinguish product/runtime coverage, reported-run mechanical checks, semantic grading and release certification. Record actual full then final-focused results; never call M5 complete while live executor/isolated replay, real quality, hosted CI, recorded demo and release remain pending. Preflight has authorization=null, zero reservations and no live executor; template grades stay null. Source/business0023 and old frozen experiments/ledgers stay unchanged. Update current status and bilingual CLI/setup/ADR/changelog links together; retain M34 results as dated evidence.

ADR0076 introduces synchronous M1 assistant/tasks and source head20261031_0020, without automatically upgrading the installed database. Keep paired PROJECT_ASSISTANT_M1 guides, Agent plan/status, backend/setup/ADR indexes and changelogs synchronized. M1 passed user-selected Agent-run local substitute/native/desktop verification; M2–M5 are still planned. Do not conflate new typed raw/code/knowledge reports with QuestionRead, or task-envelope persistence with async runner/recovery. Preserve historical schema announcements as dated context and frozen quality/ledgers.

行为变化时，在同一轮更新对应文档。根目录保留中英文 README，其余项目文档使用中文。下方各轮的双语说明记录当时的维护方式。

## 何时使用

- 修改 API 形状、数据模型、迁移版本、能力状态。
- 新增或变更架构决策。
- 准备提交、发版、写验收记录。
- 发现文档与代码不一致。

## 更新矩阵

| 改动 | 必须更新 |
| --- | --- |
| API 路径、字段、错误码、分页 | `docs/API_CONTRACT.md`、`backend/README.zh-CN.md` |
| 实体、关系、证据、时序语义 | `docs/KNOWLEDGE_MODEL.md`；必要时 ADR |
| 架构边界、存储选型、任务模型 | `docs/adr/` 新 ADR，并更新 ADR 索引 |
| 能力状态、安装方式、仓库结构 | `README.md`、`README.zh-CN.md`、`PLANS.zh-CN.md`、`docs/ROADMAP.md` |
| 前端结构、交互、组件职责 | `docs/FRONTEND.md` |
| 环境、命令、端口、配置项 | `docs/DEVELOPMENT_SETUP.zh-CN.md`、`backend/README.zh-CN.md` |
| 每次行为变化 | `CHANGELOG.zh-CN.md` 的 `Unreleased` |
| 安全、贡献流程 | `SECURITY.md`、`CONTRIBUTING.md` |

## 文档语言

根目录的 `README.md` 为英文，`README.zh-CN.md` 为简体中文，两版在页首提供语言切换链接。同步两版的功能说明、命令、状态和文档链接。引用评测语料时保留原文。

## 状态标注

- 已实现：写清当前行为、限制和验收状态。
- 规划中：明确写“规划中/尚未实现”，不得描述成已有能力。
- Mock：必须标注“演示数据”，不能与真实接口混写。
- 待验收：区分“单元测试通过”和“真实服务/真实模型通过”。

## ADR 流程

- 触发：存储选型、任务执行模型、抽取/审核边界、正式图谱写入等架构级决策。
- 命名：`docs/adr/NNNN-kebab-title.zh-CN.md`。
- 内容：Status、Date、Decision、Consequences；写清边界和未做的事。
- 更新 `docs/adr/README.zh-CN.md` 索引。
- 决策改变时新增 ADR 标明取代关系，不直接改写旧 ADR 的结论。

## CHANGELOG

- 变化写在 `## Unreleased` 下，按 `Added` / `Changed` / `Known limitations` 分组。
- 只写用户可感知的行为，不写“重构了某文件”。
- 已知限制要具体：哪些验证没做、哪些能力仍是 Mock。

## 漂移检查

提交前用几分钟核对：

- 迁移 head：`alembic heads` 与文档里的“预期版本”是否一致。
- 能力列表：README 的“当前状态”是否仍与代码一致。
- 图谱/检索/问答：是否仍被错误描述为已实现或未实现。
- 搜索关键词：`尚未实现`、`规划中`、`Mock`、`待验收`，逐个确认。
- 检查 ADR 索引和 README 文档索引中的链接。
- 错误结构、分页参数、状态枚举是否在 API 文档中更新。

本轮已同步的典型漂移（保留为检查示例）：

- 正式图谱落地后，`README.md`、`docs/ARCHITECTURE.md`、`docs/ROADMAP.md`、`backend/README.zh-CN.md` 曾仍写“尚未实现”。
- 迁移 head 变为 `0005` 后，`docs/DEVELOPMENT_SETUP.zh-CN.md` 与后端 README 曾仍写预期 `0004`。
- ADR 0007 落地后，`docs/adr/README.zh-CN.md` 的既有决策索引曾缺少条目。
- `CHANGELOG` 曾缺少图谱写入记录。

这些现在已修正；下次改行为时按上面的检查项重新核对。

## 完成检查

- [ ] 行为、文档、测试三者描述一致。
- [ ] 相关文档同轮更新，链接有效。
- [ ] 规划中/已实现/Mock/待验收标注准确。
- [ ] CHANGELOG 已更新。
- [ ] ADR 索引与新增决策一致。
- [ ] 文档中的命令实际可执行（或明确标注前提）。

## 2026-10-26 功能补全更新

2026-10-26 功能状态以 FUNCTIONAL_COMPLETION_20261026 双语报告与 ADR 0056–0059 为准；旧日期检查点保留历史数字。区分已实现、临时 schema 功能验证、真实公开模型实验、私有授权待验收及人工覆盖率 0%。

## 2026-10-29 当前优化边界

Current root README/PLANS/ROADMAP/FRONTEND consolidate capabilities; pre-20261029 snapshots live under docs/archive/pre-optimization-20261029 with corrected relative links. Preserve dated experiment/acceptance numbers. Update ADR0060–0063, exact API context/error shape, schema readiness, holdout separation and benchmark scope in paired language docs. Do not convert deferred human grading into achieved quality. Report current database0018 separately from older historical checkpoints.

## Single-project multi-agent extension (ADR0064–0065)

Current extension is ADR0064–0065, docs/MULTI_AGENT.zh-CN.md, with agent_runs migration0019. Update actual canonical tree and legacy aliases, shared/per-role attempted-call limits, explicit human resume, synchronous event persistence and lack of crash-node recovery. Keep root/backend/setup/API/frontend/knowledge-model/plan/changelog paired where companions exist. Preserve historical0018 reports and frozen experiments. Do not describe stub protocol tests as new real-provider quality or completed human grading.

## Batched lexical v2 (ADR 0066)

Current BM25/source-aware BM25 and the RRF lexical leg use v2 identifiers, 200-entity keyset batches, a 50k scan ceiling, global corpus statistics, 32 ranking quotes per canonical entity and the existing text limits. Document matched_count/results_truncated separately from omitted scan/text. Update API/current plans/backend README and bilingual ADR/changelog together; keep v1 experiment assets and historical performance/quality reports unchanged. Synchronous batching does not establish cross-request resume, repeatable-read isolation or measured v2 production capacity.

## Durable agent progress (ADR 0067)

Current agent events and call reservations persist during synchronous execution; validated code/answer and committed extraction IDs have checkpoints. Replace current end-only persistence descriptions, preserve historical acceptance reports, and describe primary status vs partial result, pending-write refusal, lease fencing, conservative reservations and lack of automatic paid continuation. Schema/head remains0019. Sync API, MULTI_AGENT, architecture, frontend labels, backend READMEs, plans, changelog and paired ADR; stub integration is not provider quality.

## Explicit workflow scope (ADR 0068)

WorkflowRead.scope projects only retrieval_mode/valid_at/include_code_analysis/code_strategy/snapshot_id/version_ids from existing requests; do not document raw request exposure or a migration. Current UI supports choices, timezone-aware history, draft vs saved scope and read-only context retry, replacing the initial default-context-only page description. Keep BM25 default, unspecified-local-latest-at-execution semantics, truncation, backend validation and no automatic replay explicit. Pair MULTI_AGENT/backend README/plans/changelog/ADR updates; synthetic snapshot browser fixtures are not new remote acceptance.


## Cloudflare judge documentation (ADR0072)

Current anonymous grading can select Jev or CF; ADR0072 extends ADR0070 without rewriting historical experiments. Sync CF/Jev guide pairs, setup/backend README pairs, current README/plans/roadmap/architecture and changelogs. Document native ai/run envelopes, explicit decision/chat formats, generic CLI authorization, credential placeholders, unchanged business providers, null chat confidence/usage when absent and CF model revision limits. Local substitutes/preflight are not live compatibility or quality, and human coverage remains0%. Keep holdout and frozen outputs unchanged.


## OpenRouter judge documentation (ADR0073)

Sync OPENROUTER_EVALUATION language pair, ADR/index pair, provider guide introductions, setup/backend README pairs, current plans/architecture/roadmap/changelogs and AGENTS pair. Distinguish OpenRouter typesafe/jev-1.14 from CF/direct names, release selection from dated snapshots, actual per-response identity/model-drift stopping, optional reported cost and immutable attempt records. The TypeSafe-only flag cannot authorize OpenRouter. No SDK/business provider/schema change; local HTTP substitutes and zero-call preflight do not prove account/payment/model quality. Keep human0, holdout/frozen artifacts and prior CF smoke/old provider ledgers untouched.
