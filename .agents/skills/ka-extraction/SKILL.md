---
name: ka-extraction
description: Knowledge Atlas 的 DeepSeek 候选知识抽取。修改抽取 Schema、提示词、证据校验、抽取任务或租约，排查 EXTRACTION_* 失败，或验收真实模型时使用。触发词：extract, DeepSeek, candidate, evidence, chunk, prompt, 抽取, 候选, 证据.
---

# 候选知识抽取

模型只生成候选，不写权威表；每个候选必须能回到原文。实现入口：`backend/app/services/knowledge.py::run_extraction`、`backend/app/services/deepseek.py`、`backend/app/schemas/knowledge.py`。

## 何时使用

- 修改抽取 Schema、提示词、模型参数或证据规则。
- 排查 `EXTRACTION_*` 错误、候选为空、证据不匹配。
- 验收真实 DeepSeek 调用。
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
