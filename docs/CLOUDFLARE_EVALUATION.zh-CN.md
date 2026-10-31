# Cloudflare Workers AI 匿名自动评审

真实holdout-v3 Clef评审已按用户明确授权完成457次请求，见[模型结果与边界](../evaluation/results/2026-10-31-holdout-v3-clef-run1/REPORT.zh-CN.md)。不产生人工评分、校准或不可变权重结论。下文适配开发/预演示例保留为历史，完成本轮不授权后续调用。

[English](CLOUDFLARE_EVALUATION.md)

OpenRouter Jev 已作为独立[离线适配](OPENROUTER_EVALUATION.zh-CN.md)提供。使用本指南时明确 --provider cloudflare，新环境示例选择 openrouter。CF 原生适配不包含第三方 Jev 统一路由。

离线评审新增 Workers AI，可与 [Jev](JEV_EVALUATION.zh-CN.md) 显式选择。人工评分覆盖率仍为0%，正式知识入图仍须人工审核。本地 HTTP 替身验证不证明真实兼容、质量、延迟或账单；开发期间没有真实供应商调用。

## 本机配置

`backend/.env` 和 `.env.example` 包含以下占位字段。账号 ID 与 Workers AI API Token 由用户在本机填写，不提交或发送 Token。

```dotenv
EVALUATION_PROVIDER=cloudflare
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_MODEL=@cf/cloudflare/clef-flash
CLOUDFLARE_JUDGE_MODE=decision
CLOUDFLARE_TIMEOUT_SECONDS=60
CLOUDFLARE_MAX_TOKENS=2048
```

账号 ID 为32位十六进制字符，Token 创建步骤见[官方指南](https://developers.cloudflare.com/workers-ai/get-started/rest-api/)。原 Jev 字段保留；未设置 `EVALUATION_PROVIDER` 时仍默认 `jev`，新环境示例选择 OpenRouter。无需新增 SDK 或依赖。

## 请求格式

两种模式都通过 `POST https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}` 与 Bearer 认证调用，再解析 `success/result/errors` 外层。不自动发现模型、切换格式或回退供应商。

| 模式 | 配置与请求 | 输出 |
| --- | --- | --- |
| `decision` | `@cf/cloudflare/clef` 或 `@cf/cloudflare/clef-flash`；发送短名 `model=clef` / `clef-flash`、`state`、`questions` | 校验模型标识、Choice 标签、有限概率和置信度 |
| `chat` | 支持 `messages` 和 JSON Schema `response_format` 的文本模型 | 仅校验 Choice 标签，置信度/概率保持 null |

普通文本模型需要同时修改两项，例如：

```dotenv
CLOUDFLARE_MODEL=@cf/qwen/qwen3-30b-a3b-fp8
CLOUDFLARE_JUDGE_MODE=chat
```

此适配器不覆盖全部目录任务：嵌入、重排、语音、图像生成及不支持所需结构化输出的文本模型不在接口范围内。不支持的请求会失败且不重试。模型可用性及能力以其当前页面为准。依据：[Clef](https://developers.cloudflare.com/workers-ai/models/clef/)、[Qwen](https://developers.cloudflare.com/workers-ai/models/qwen3-30b-a3b-fp8/)、[JSON Mode](https://developers.cloudflare.com/workers-ai/features/json-mode/)。

## 零调用准备与预演

在 `backend` 执行，每次使用新输出目录：

```powershell
.\.venv\Scripts\python.exe -m scripts.judge_evaluation prepare --dataset ../evaluation/public-v2 --predictions ../evaluation/results/2026-10-26-public-v2-run1/bm25.jsonl --output ../output/cf-my-run/packet
.\.venv\Scripts\python.exe -m scripts.judge_evaluation run --provider cloudflare --packet ../output/cf-my-run/packet --output ../output/cf-my-run/preflight
```

预演无需 Token/账号，不发 HTTP 请求；校验包哈希、配置及最终请求的24000字节 UTF-8 JSON 上限。检查 `run.json` 的 `planned_requests`、`requested_model`、`judge_config` 和 `judge_config_sha256`；预留/完成/评分均0。历史20题示例计划54次。切换模型/模式后需重新预演、保存新报告。使用 holdout 前固定裁判和协议，不根据 holdout 结果选择裁判。

输入包与供应商无关，兼容保留 `jev-anonymous-claims-v1` 格式标识。原 `scripts.jev_evaluation` 导入/命令仍可用；环境选择 Cloudflare 后，Jev 运行显式指定 `--provider jev`。

## 后续单独授权的真实运行

以下仅记录未来用法，配置凭据并明确授权供应商及次数后执行。其他输入包按实际预演次数替换54：

```powershell
.\.venv\Scripts\python.exe -m scripts.judge_evaluation run --provider cloudflare --packet ../output/cf-my-run/packet --output ../output/cf-my-run/live --allow-judge-calls --max-requests 54
```

`--allow-jev-calls` 不能授权 Cloudflare。每次 HTTP 前落盘预留；失败/未知结果计数并停止，不自动重试或续跑，已有输出目录拒绝覆盖。每次新真实运行都需单独授权，不重置既有84次模型/61次嵌入账本。API/Worker/页面读取不触发评审；业务 DeepSeek 生成和嵌入接入不变。

## 解读与限制

匿名化、原文引文验证、基于参考事实的正确性/完整性/拒答判断和只看引用的支持判断保持一致，每个被引用单元交换选项顺序评审两次。报告记录供应商/模型/模式/协议/配置哈希、判定和实际用量；CF 缺失用量保持 null。CF 目录 ID 不是已核验的不可变权重版本，报告标记 `model_revision_pinned=false`；chat 未返回模型标识时保持 null。

chat 标签的 `confidence=null`、`probabilities=null`，不把生成置信度当校准概率；即使两次选项一致，也保守计入 `uncertain_units`。decision 选项顺序分歧或置信度低于0.8也标记不确定，阈值未在本项目校准。这些是模型判断，不是人工正确率或语义蕴含证明，人工评分字段保持空白。

响应流限制128 KiB，有限超时，无重定向/重试。重复键、Markdown 包裹的 JSON、缺少/多余答案、非法选项、不完整输出及非法用量被拒绝。报告不复制供应商正文、原始提示词、凭据或生成解释。不改数据库结构、业务 API、页面或入图行为。
