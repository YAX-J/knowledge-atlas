# OpenRouter Jev 匿名自动评审

[English](OPENROUTER_EVALUATION.md)

离线评审新增 `openrouter`，与直连 TypeSafe 的 `jev` 和原生 `cloudflare` 适配器并列，此渠道仍使用 Jev。人工评分覆盖率保持0%，正式知识入图仍须人工审核。本轮只做 HTTP 替身和零调用预演，不代表真实账号、付款或模型质量验收。

## 配置

在 `backend/.env` 本机填写密钥，不发送、不提交。真实本地环境及 `.env.example` 包含：

```dotenv
EVALUATION_PROVIDER=openrouter
OPENROUTER_API_KEY=
OPENROUTER_MODEL=typesafe/jev-1.14
OPENROUTER_TIMEOUT_SECONDS=60
```

密钥创建见 [OpenRouter 设置](https://openrouter.ai/settings/keys)。积分、付款和地区可用性须在自己的账号确认，代码接入不证明账号符合条件。本地评审选择改为 OpenRouter，原 CF/TypeSafe 凭据保留；未设置供应商字段时仍默认 `jev`。无需新增 SDK 或依赖。

## API 与模型标识

适配器通过 Bearer 认证调用 `POST https://openrouter.ai/api/alpha/decisions`，发送 `model`、`state`、`questions` 和 `provider.allow_fallbacks=false`。不使用聊天补全、CF `input` 外层或 `/v1/systemone`。仅覆盖本项目评审需要的 Choice 判断，不泛化为所有 OpenRouter 模型或业务问答/抽取/嵌入切换。

OpenRouter 模型 ID 使用 `typesafe/jev-1.14`，与 CF/直连的 `jev-1.14.0` 写法不同。接受明确的 `typesafe/jev-<major>.<minor>` 发布选择或带日期的快照 ID，`latest` 别名和无版本 ID 在 HTTP 前拒绝。发布选择可能返回带日期 ID，如官方示例 `typesafe/jev-1.13-20260917`，需保留实际返回值。只接受请求的同一发布版本及合法八位日期后缀；显式指定快照时必须完全一致。

发布选择不是不可变快照，标记 `model_revision_pinned=false`。`run.json` 记录 `requested_model`、各次实际模型、裁判配置/哈希及 `resolved_model`。同批实际模型变化时保留两次结果和尝试，标记失败并在下次请求前停止。不用 holdout-v3 选择裁判或调整提示词/阈值，使用前冻结协议。依据官方 [Jev 指南](https://openrouter.ai/docs/guides/community/jev)、[返回示例](https://openrouter.ai/docs/guides/community/jev-tutorial) 和 [Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request)。

## 零调用准备与预演

在 `backend` 执行，每次使用新输出目录：

```powershell
.\.venv\Scripts\python.exe -m scripts.judge_evaluation prepare --dataset ../evaluation/public-v2 --predictions ../evaluation/results/2026-10-26-public-v2-run1/bm25.jsonl --output ../output/or-my-run/packet
.\.venv\Scripts\python.exe -m scripts.judge_evaluation run --provider openrouter --packet ../output/or-my-run/packet --output ../output/or-my-run/preflight
```

预演无需 API Key，不发 HTTP 请求；校验包完整性、模型选择及最终请求24000字节 UTF-8 JSON 上限。查看 `run.json` 的计划次数和配置，预留/完成/模型评分均0。历史20题 BM25 示例计划54次；旧平铺答案保留整答粒度，新结论导出保留逐条归属。共用供应商无关输入包，原 `scripts.jev_evaluation` 入口继续可用。

## 后续单独授权的真实运行

以下仅作说明，本轮没有真实请求。填入密钥并明确授权供应商及次数后执行：

```powershell
.\.venv\Scripts\python.exe -m scripts.judge_evaluation run --provider openrouter --packet ../output/or-my-run/packet --output ../output/or-my-run/live --allow-judge-calls --max-requests 54
```

其他输入包以实际计划次数为准。`--allow-jev-calls` 只授权直连 TypeSafe，不能授权 OpenRouter。每次 HTTP 前落盘预留，失败/超时/未知结果计数；错误停止，不自动重试/续跑，已有输出目录拒绝覆盖。新目录不清除旧用量或自动增加预算。OpenRouter 授权独立于历史84次模型/61次嵌入账本和 CF 冒烟尝试，不重置或复用这些记录。API/Worker/页面读取不触发评审。

## 输出、网络与限制

保留匿名输入、原文校验、基于参考事实的正确性/完整性/拒答与只看引用的支持判断。校验全部答案键、Choice、有限概率和置信度，保留交换选项顺序的两次判断；分歧或置信度低于0.8标记不确定。这些概率/阈值不证明项目校准准确率或人工一致性，人工评分字段保持空白。

用量要求非负整数输入/输出计数，`usage.cost` 为供应商提供的有限非负美元金额，缺失时 null；不补造费用或推断精确账单。拒绝错误模型、非法/重复 JSON、缺项/多余判断及非法用量。响应流限制128 KiB、有限超时、不重定向。HTTPX 默认 transport 保留环境/系统代理发现，重试次数0；连接/读取超时提供独立脱敏错误码，认证/付款/限流也使用静态错误码，不输出原始错误正文或凭据。客户端及请求均不启用供应商回退。

本轮不实现另一条 CF 第三方 Jev 统一路由。此前本地 CF 冒烟中的400/402/超时保留为历史记录，不属于成功 Jev 评估；直连 TypeSafe 和 CF 原生评审仍可显式选择。
