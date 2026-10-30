# Jev 匿名自动评审

[English](JEV_EVALUATION.md)

通过 OpenRouter 使用 Jev 时见独立 [OpenRouter指南](OPENROUTER_EVALUATION.zh-CN.md)，选择 --provider openrouter。直连 TypeSafe 的密钥/模型字段及 --allow-jev-calls 仍只适用于直连 TypeSafe。

匿名评审支持直连 TypeSafe Jev、OpenRouter Jev 和 [CF原生适配](CLOUDFLARE_EVALUATION.zh-CN.md)，本页说明直连 TypeSafe。人工覆盖率仍为0%，正式知识须人工审核。历史20题 BM25 预演计划54次，预留/完成均0；开发期间没有真实裁判调用或质量评分。[ADR0072](adr/0072-cloudflare-judge-adapter.zh-CN.md) 扩展 ADR0070 的 Jev 单供应商限制，旧实验和人工字段不改。

## 配置

backend/.env 与 [.env.example](../backend/.env.example) 已添加以下字段。开发完成后由用户在本机填密钥，不发送到聊天，也不提交 .env。

```dotenv
TYPESAFE_API_KEY=
TYPESAFE_MODEL=jev-1.14.0
TYPESAFE_BASE_URL=https://api.typesafe.ai
TYPESAFE_TIMEOUT_SECONDS=60
```

适配器使用已有 httpx 和官方 [System One API](https://docs.typesafe.ai/api/system-one)，无需安装 SDK。拒绝模型别名、校验实际版本，响应最多128 KiB、请求最多24000字节 UTF-8 JSON，不自动重试。字节保护不等于 token 数、准确率或费用估计。

## 零调用准备与检查

在 backend 执行，每次使用新输出目录：

```powershell
.\.venv\Scripts\python.exe -m scripts.jev_evaluation prepare --dataset ../evaluation/public-v2 --predictions ../evaluation/results/2026-10-26-public-v2-run1/bm25.jsonl --output ../output/jev-my-run/packet
.\.venv\Scripts\python.exe -m scripts.jev_evaluation run --provider jev --packet ../output/jev-my-run/packet --output ../output/jev-my-run/preflight
```

每种方法的导出须覆盖全部题目并包含真实答案文本。准备时重查引用精确原文行，创建打乱后的匿名包，方法/题目映射另存，裁判输入不带方法、生成模型/置信度或原题 ID。旧平铺导出保留 legacy_answer 整答粒度，新的公开验收导出提供 claims 与 claim_evidence 才做逐条检查，不将旧回答补拆成虚构条目。

预演校验输入包哈希、固定模型和字节保护，输出 status=prepared、计划次数、预留/完成/模型评分均0、人工覆盖率0，无需密钥。示例计划54次：每答一次质量请求，每个有引用单元交换选项顺序各一次。输入包及清单应保持不变。

## 后续单独授权的真实运行

以下只记录未来用法，本轮没有执行：

```powershell
.\.venv\Scripts\python.exe -m scripts.jev_evaluation run --provider jev --packet ../output/jev-my-run/packet --output ../output/jev-my-run/live --allow-jev-calls --max-requests 54
```

其他输入包按预演实际计划次数设上限；预算不足或未配密钥时在传输前失败。每次请求先落盘预留，失败和未知结果也计数；出错停止、不自动重试，不覆盖或恢复已有输出。Jev 预留独立于旧84次模型/61次嵌入账本，每次新真实运行需独立明确调用授权。API、Worker、页面刷新或 GET 都不会启动评审。

## 解读结果

正确性、必需事实覆盖、拒答合理性是使用参考事实的独立 Choice 问题。引用判断只看单条结论和它实际引用的上下文，不看参考答案；上下文为精确引文范围前后最多3行。两种选项顺序均保存，不一致或置信度低于0.8标为不确定，不自动确认结论。阈值由协议固定，不代表在本项目上校准过的准确率。

run.json 保存选项/概率、实际模型、用量、输入哈希、调用预留、评审粒度和不确定标记，均作为模型判定。不能写入人工 answer_correct/explainability_score 字段或宣称用户一致性。参考标注可能由 Agent 编制，不是人工评分。Jev 不生成解释正文。holdout-v3 继续隔离：使用前冻结评审协议，不根据其结果调排序、提示词或阈值。参考官方[引用示例](https://docs.typesafe.ai/cookbooks/citation_check)和[已知限制](https://docs.typesafe.ai/model-jaggedness/jev-1.13)。
