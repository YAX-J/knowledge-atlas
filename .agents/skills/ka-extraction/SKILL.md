---
name: ka-extraction
description: Knowledge Atlas 的 DeepSeek 候选知识抽取。修改抽取 Schema、提示词、证据校验、抽取任务或租约，排查 EXTRACTION_* 失败，或验收真实模型时使用。触发词：extract, DeepSeek, candidate, evidence, chunk, prompt, 抽取, 候选, 证据.
---

# 候选知识抽取

模型只生成候选或基于已选证据生成回答，不直接写权威表；每个候选和支持性回答都必须能回到原文。候选入口：`backend/app/services/knowledge.py::run_extraction`、`backend/app/services/deepseek.py`、`backend/app/schemas/knowledge.py`；回答入口：`backend/app/services/questions.py`、`backend/app/schemas/questions.py`。

## 何时使用

- 修改抽取 Schema、提示词、模型参数或证据规则。
- 排查 `EXTRACTION_*` 错误、候选为空、证据不匹配。
- 验收真实 DeepSeek 调用。
- 修改证据问答提示词、严格回答 Schema 或引用边界。
- 调整抽取任务、租约或输入上限。

## 链路（按顺序理解）

1. `POST /api/v1/sources/{source_id}/extract` → `run_extraction`。
2. 短事务内对来源行加锁，读当前任务；已成功直接返回，不调用模型。
3. 校验：来源属于当前用户/项目、`status == ready`、已配置密钥、分块非空、≤100 块、输入 JSON ≤ `extraction_max_input_chars`。
4. 写入/复用任务：`running`、`extracting`、新 `execution_id`、租约、`attempt_count + 1`，提交并释放锁。
5. 网络调用 `deepseek.extract_candidates`，只传分块快照。
6. 逐项校验证据：分块必须属于本来源；`quote` 必须逐字存在于该分块；行号由后端用分块原文重算。
7. 用 `execution_id` 做 fencing 更新任务；成功才 `add_all(候选)`，整批原子提交。

## 不可违反的规则

- 模型输出不可信：Schema 校验、类型白名单、引用校验一个都不能省。
- `chunk_id` 只能来自本次输入；`quote` 必须逐字存在；模型给的行号一律丢弃。
- 整批全存或全不存；不允许保存部分候选。
- 不自动重试模型请求（可能重复计费）；失败由用户手动重试。
- 不记录提示词、补全内容、密钥或完整敏感源码；日志只记录错误类型。
- 实体类型只允许 `schemas.knowledge.EntityType`，关系只允许 `RelationType`。
- 关系两端必须引用本次输出中的实体 `local_id`，且输出内 `local_id` 唯一。

## 关键标识与上限

| 项 | 值 / 位置 |
| --- | --- |
| 抽取任务 ID | `uuid5(source_id, PROMPT_VERSION)` |
| 提示词版本 | `deepseek.PROMPT_VERSION`，当前 `knowledge-candidates-v1` |
| 任务类型 | `knowledge_candidates`（解析 Worker 不消费） |
| 单次分块 | ≤100 块 |
| 输入字符 | `EXTRACTION_MAX_INPUT_CHARS`，默认 60000 |
| 输出条数 | 实体 ≤50，关系 ≤100 |
| 响应大小 | 原始响应 ≤1 MiB |
| 输出 token | `max_tokens=8192` |
| 租约 | `max(TASK_LEASE_SECONDS, ceil(DEEPSEEK_TIMEOUT_SECONDS)+60)` |

## 修改流程

### 加字段或类型

1. 改 `backend/app/schemas/knowledge.py`，同步 `EntityType`/`RelationType`。
2. 升 `PROMPT_VERSION`。**不升版本会复用旧成功任务，新提示词永远不生效。**
3. 改 `run_extraction` 的 payload 组装与 `deepseek.py` 的提示词说明。
4. 改 `tests/test_knowledge.py` 的 `parsed_source` 夹具与断言。
5. 同步 `docs/KNOWLEDGE_MODEL.md`、`docs/API_CONTRACT.md`、`backend/README.md` 与中文版。
6. 需要新列时按 `ka-migrations` 加迁移。

### 改提示词

- 只改 `SYSTEM_PROMPT` 文案也要升 `PROMPT_VERSION`。
- 升版本后旧候选仍在旧任务下，新旧批次不会互相覆盖；确认前先核对来源。
- 用固定夹具回归：2 实体 + 1 关系、空结果、单实体、非法引用各一组。

### 改任务/租约

- 抽取是同步 HTTP，不是 Worker 任务；不要在 `app/worker.py` 增加模型消费。
- 租约必须大于模型超时，否则并发第二次请求可能接手。
- 保留 `EXTRACTION_RUNNING`（租约有效）与 `EXTRACTION_REPLACED`（旧执行写入被拒）语义。

## 测试配方

```python
from app.schemas.knowledge import ExtractionDraft
from app.services import deepseek

def fake_extract(settings, chunks):
    assert chunks and all("chunk_id" in c and "content" in c for c in chunks)
    return ExtractionDraft.model_validate(draft)

monkeypatch.setattr(deepseek, "extract_candidates", fake_extract)
response = client.post(f"/api/v1/sources/{source['source_id']}/extract")
```

可直接复用 `tests/test_knowledge.py` 的 `configured`、`parsed_source`、`reviews`，以及 `tests/test_graph.py` 的 `extracted`。必须覆盖：

- 成功：候选数、任务状态、证据行号、重复调用只调一次模型。
- 伪造引用：`quote` 不在分块中 → 任务 `failed`，`error.code == "EXTRACTION_EVIDENCE_INVALID"`，候选数为 0。
- 跨来源 `chunk_id`、未知类型、重复 `local_id`、关系端点不存在。
- 未配置密钥 → HTTP 503；未解析 → HTTP 409；超限 → HTTP 413。
- 租约有效时再次请求 → HTTP 409；租约过期可接手。

## 真实模型验收

1. `backend/.env` 配 `DEEPSEEK_API_KEY`，不要把密钥写进前端、夹具或日志。
2. 重启 API，上传一篇短篇公开 Markdown 并完成解析。
3. 页面点击“提取候选知识”，逐条核对：名称、摘要、置信度、引用是否逐字、行号是否准确。
4. 记录结果到 `PLANS.md`/`CHANGELOG.md` 的已知限制或验收记录；模拟测试不能替代真实质量结论。

## 证据问答边界

- `POST /projects/{project_id}/questions` 同步且不持久化，复用混合检索，最多 5 个实体、12 条输入证据和 5 条输出引用。
- 只把问题和选定证据发送给模型；`supported=true` 必须引用证据，`supported=false` 必须说明缺失信息。
- `questions.py` 必须验证每个引用 UUID 属于本次检索集合；未知引用返回 `QUESTION_EVIDENCE_INVALID`，不能降级为无引用回答。
- 没有检索证据时不调用回答模型。不得记录问题、提示词、回答正文或完整证据。
- 回答提示词当前没有任务复用语义，不使用候选抽取的 `PROMPT_VERSION`；修改输出结构时同步 `tests/test_questions.py`、API 契约与 ADR 0011。

## 多语言调用 Agent 边界

- `POST /sources/{source_id}/agent-call-analysis` 默认是显式、同步、非持久化的 single_step；可选 tools 使用 call_tools.PROMPT_VERSION 和授权快照只读工具，最多 4 轮模型、8 次工具、累计工具结果 20000 字符、累计输入 240000 字符及轮间 230 秒检查。最终使用同一严格 Schema 与证据校验（ADR 0043）。
- 本地语法分析先提供调用 ID、同仓库兼容语言族的声明候选 ID、路径和精确原文行；模型不能访问数据库、扩展候选或写正式图谱。
- 每个输入调用必须且只能返回一条决定；目标只能来自该调用的候选集合，`resolved/ambiguous/unresolved` 与目标数量必须一致。后端拒绝缺项、重复和伪造 ID。
- 没有候选时不调用模型。最多 99 份相关来源/20 MiB、100 个候选调用、每调用 20 个候选，并遵守 `extraction_max_input_chars`。
- 不记录提示词、完整源码或模型原始响应；前端只展示精确行证据、置信度和简短 `resolution_basis`，不展示思维过程。
- 测试使用 `tests/test_code_agent.py` 的模拟输出；真实质量、成本、延迟和提示注入验收必须单独注明。

## 常见失败

| 错误码 | 常见原因 | 处理 |
| --- | --- | --- |
| `EXTRACTION_NOT_CONFIGURED` | 未配 key 或未重启 | 配 `DEEPSEEK_API_KEY` 后重启 |
| `SOURCE_NOT_PARSED` | 来源未 ready | 先解析 |
| `SOURCE_HAS_NO_CHUNKS` | 空文档 | 换有内容的资料 |
| `EXTRACTION_INPUT_TOO_LARGE` | 超过块数/字符 | 拆分文件 |
| `EXTRACTION_PROVIDER_FAILED` | 网络/认证/余额/限流 | 检查 key 与账户，手动重试 |
| `EXTRACTION_OUTPUT_INVALID` | 非法 JSON、未完整结束、超 1 MiB | 缩小资料后重试 |
| `EXTRACTION_EVIDENCE_INVALID` | 引用不存在或非逐字 | 通常需重试；持续失败检查提示词 |
| `EXTRACTION_RUNNING` | 有效租约内重复请求 | 等待或刷新 |
| `EXTRACTION_REPLACED` | 旧执行被接手 | 刷新，用新结果 |

## 完成检查

- [ ] `python -m pytest tests/test_knowledge.py tests/test_graph.py` 通过。
- [ ] 新增/修改的 Schema 有正反用例。
- [ ] `PROMPT_VERSION` 已按需升级。
- [ ] 文档双语已同步（见 `ka-docs-sync`）。
- [ ] 没有把密钥、提示词全文或模型原始响应写进日志/测试/文档。
- [ ] 实际运行过的命令已记录，未运行的检查明确说明。

## Question passage attribution (ADR 0047)

Exact source/chunk/line/quote deduplication retains related_entities from retrieved candidates and supplies entity_names in answer context. Preserve the canonical citation ID, primary entity_id/entity_name and response entity_ids attribution rules. Never merge stored evidence or collapse distinct sources/versions. Verify attribution and single-passage display with tests/test_knowledge_discovery.py and frontend/tests/discovery.test.ts; provider quality remains separate.

## Question source-aware mode and uncertain outcomes

Question retrieval accepts bm25_source without embeddings, but supported answer generation still requires explicit provider use. Retain citation UUID and evidence/support validation. New misleading-overlap refusal cases use stub answers and are not real model-quality grades. Legacy one-shot questions and call analysis remain non-persistent; durable embedding_jobs does not create question history or resume Agents. Client writes with lost results are uncertain and must never be described as rolled back.

## 2026-10-26 功能补全更新

持久化会话每轮重新检索，六轮历史是提示，不能提供可引用证据；请求 UUID 与 execution UUID 分开，未知结果先查询，明确付费重试。问答默认 RRF，仍可 BM25。public-v2 金标为 Agent 编制，真实人工评分不得自动生成。

## 2026-10-29 当前优化边界

holdout-v3 contains genuine pinned public documentation, not private personal notes; 24 Agent-authored cases/gold annotations are not human grades. Keep v1/public-v2 development and v3 test separate; never tune against v3. Current cumulative paid ledger is84 model/61 embedding (authorization120/160), not reset per directory. User explicitly defers human grading. No new provider experiment or score is implied by fixture validation/replay.

## Single-project multi-agent extension (ADR0064–0065)

Canonical prompts/provider/usage are app/llm/{prompts.py,providers/deepseek.py,usage.py}; old services imports alias these modules. Extraction and QA now delegate to registry agents. Legacy single-step API keeps old prompt/task identity; tools extraction uses :tools-v1 and exact same evidence validation. Default extraction GET selects the most recently created legacy/tools task. Shared runtime counts failed model/embedding attempts before requests. Code hints cannot become evidence; empty QA refuses before providers, unknown citations fail. Coordinated candidates wait for existing human review. API read/list/resume never call providers; do not invent human evaluation scores.

## Coordinated progress (ADR 0067)

Only coordinated RunContext instances attach the application progress sink. It commits event metadata/reserved budgets before callbacks, refuses pending ORM writes, and fences/renews active execution ownership. Keep extraction claim and validated-candidate commits intact; extraction checkpoints contain IDs after that commit, never unvalidated drafts. Storage failure stops later calls. Partial code/answer results remain readable after failure; GET/same-UUID replay do not resume paid nodes. A pre-call reservation is conservative, not a billing receipt. No prompt/version or schema change is implied.


## Claim-level QA (ADR 0069)

Live single-step and tool QA parse ClaimAnswerDraft with 1–8 supported/insufficient claims; supported claims require unique per-claim citations, insufficient claims cannot cite. At most five distinct citations and 4000 joined characters; overall support matches all-claim support, partials require missing information. Derive flat answer/citation union on the server and validate every UUID against the scoped current pool. No flat-output fallback, extra model judge or automatic retry. Legacy AnswerDraft is diagnostic-only; old persisted JSON defaults claims/protocol to null without inferred mappings or paid replay. ANSWER_PROMPT_VERSION=evidence-claims-v2 is separate from extraction identity. New evaluation manifests record it; frozen outputs/holdout and paid ledger stay untouched. Citation membership is not semantic entailment.


## Current Jev evaluation decision (2026-10-30)

The user selects Jev-only anonymous grading instead of deferred human blind review. Human grade coverage remains0%; model grades cannot populate human fields. This turn is local development/verification only: TYPESAFE_API_KEY stays empty and no live Jev calls are authorized. Offline scripts.jev_evaluation prepares complete answer exports, verifies source lines, masks methods/case IDs and separates reference correctness from citation-only claim support. Pinned jev-1.14.0, per-call reservation, explicit total request cap, no retry/resume/overwrite; reversed option order and confidence flag uncertainty. Legacy flat answers keep answer-level granularity. Freeze judge protocol before holdout use, preserve historical artifacts and the existing84/61 ledger. Formal graph promotion still requires human review.


## Cloudflare offline judging (ADR0072)

The user now permits explicit Jev or Cloudflare Workers AI selection for anonymous model grading, superseding the Jev-only vendor restriction. Keep formal knowledge review human-controlled and human grading coverage0%. CF native REST decision mode supports Clef/Clef-flash state/questions; chat uses compatible text models with messages/JSON Schema labels, confidence/probabilities null and uncertain citation units. Never change business DeepSeek/embedding providers implicitly. scripts.judge_evaluation shares the legacy packet/runner; --allow-jev-calls cannot authorize CF. Preserve before-call reservations, explicit per-run caps, fail-stop/no retries/resume, fresh outputs and no live calls during this implementation. Freeze judge/protocol before holdout use; CF catalog names are not verified immutable revisions. See docs/CLOUDFLARE_EVALUATION.md.


## OpenRouter offline Jev (ADR0073)

Add explicit openrouter selection alongside direct jev and native cloudflare. It is evaluation-only: POST https://openrouter.ai/api/alpha/decisions, separate OPENROUTER_API_KEY/MODEL/TIMEOUT fields, versioned release or dated snapshot IDs and allow_fallbacks=false. Keep Choice/quote/anonymity validation, human grades0%, formal human promotion, proxy support, before-call reservations, no retry/resume/fallback and distinct provider authorization. Record actual dated response identities and stop on within-run drift without erasing results/attempts. CF unified third-party Jev is not added here; frozen assets/holdout/old ledgers stay unchanged. This development turn has no live calls.

## Current-system evaluation (2026-10-31)

Use scripts.evaluation_diagnostics only for development datasets; preserve exact packet/run/configuration hashes, raw confidence/labels, whole-answer legacy granularity and human0. Observable gold gaps are not established causes or human grades. scripts.run_public_acceptance now supports frozen holdout-v3 with per-case valid_at and current questions.answer_question single_step; export claims, claim_evidence, actual answer_input_evidence and retrieval metadata. Frozen line-evidence-v2 consumes a separate metrics-input projection; do not widen the historical prediction schema. Provider/DB-free --preflight reads the historical84/61 ledger without resetting it. Holdout live use needs explicit authorization, sufficient cumulative budget and an exact --approved-plan, including code/config/data hashes and per-run caps. The prospective96 model/73 embedding upper bounds exceed remaining36 model calls; no new live calls are authorized by the offline implementation. See docs/CURRENT_SYSTEM_EVALUATION.md. Current per-entity evidence clipping remains a disclosed limitation; do not tune it against holdout.

## Explicit live holdout round (2026-10-31)

The user authorized one independent96-answer/73-embedding round, excluding judges. RoundLedger uses an existing scoped grant only, validates unchanged limits/model/dataset scope, atomically reserves before transport and claims one output; no grant creation on use, automatic retry/resume or fresh-directory replay. Preserve the historical84/61 ledger. This round failed at answer5 with QUESTION_OUTPUT_INVALID, saved4 BM25 answers and used5/1; unused91/72 is not a standing retry grant. See evaluation/results/2026-10-31-holdout-v3-run1/REPORT.md. Later diagnostics record exception classes and validation-type counts/current case only, never inputs/messages/model text; the original response details cannot be recovered. Keep holdout/prompt/ranking/threshold bytes unchanged and do not prepare incomplete judge packets.

## Explicit repaired retry: ADR0074

User requested fix and retry. Opt-in offline execution v4 isolates only QUESTION_OUTPUT_INVALID after retrieval into a null-answer case failure, preserving strict online validators and continuing distinct cases without same-case retries. Other errors remain fail-stop. Keep full denominators/coverage; never fill failed answers or human grades. A single explicitly scoped validated BM25 diagnostic export may be reused only after dataset/fixture/app/model/protocol and full ordered evidence/input equality, with unique exact-passage UUID remap and provenance/original latency. It is not legacy inference or online caching. This completed retry used diagnostic1+main95 models/73 embeddings,91 valid/5 invalid out of96. All five failures were overall_support_mismatch; no flags/prompts/ranking were repaired to fit holdout. Judge prepare defaults remain strict; --exclude-output-errors explicitly hashes5 exclusions,91 gradable/96 total. CF Clef zero-call preflight457 is NOT live authorization. See evaluation/results/2026-10-31-holdout-v3-run2/REPORT.md; prior ledgers/failed run are unchanged.

## Authorized holdout judging completed (2026-10-31)

User explicitly authorized457 CF Clef requests; all457 reserved/completed and91 reviews graded without retry/fallback/resume. The grant is exhausted; no further calls. Preserve91 valid/96 total,5 invalid-output exclusions, all prior ledgers and frozen inputs. scripts.summarize_judging is offline: verify dataset/packet/config hashes, source answer/reference/citation mapping, exact jobs, uncertainty and full/subset denominators. Never write human grades. Results:83 correct model labels,103/183 high-confidence double-order citation supports,80 uncertain, all91 abstention judgments low-confidence; human0. Quality low-confidence counts are descriptive, not reclassification. Shared22 valid cases give20 correct labels per method, not equivalence/superiority evidence. Citation context includes at most3 surrounding lines; support does not prove quote-only entailment. See evaluation/results/2026-10-31-holdout-v3-clef-run1/REPORT.md and docs/HOLDOUT_DISCUSSION_AND_DEMO.md. No holdout/prompt/ranking/threshold tuning or extra paid runs is authorized.
