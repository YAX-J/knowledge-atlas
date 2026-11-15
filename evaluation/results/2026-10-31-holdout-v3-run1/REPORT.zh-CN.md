# Holdout-v3 第一次真实运行：中途停止


2026-10-31，用户明确授权本轮最多 **96 次 DeepSeek 问答、73 次现有嵌入服务调用**，不包含裁判。使用新独立账本，保留原84/61账本；冻结的7份文档、24题、参考标注、排序、回答提示词和阈值均不改。

| 项目 | 实际记录 |
| --- | --- |
| 状态 | failed；部分结果，不是完成的四组实验 |
| BM25 | 保存4条：holdout-v3-01 至 holdout-v3-04 |
| 失败位置 | 第5次回答，按冻结顺序为 holdout-v3-05；由调用数及已保存前缀推得 |
| 错误 | `QUESTION_OUTPUT_INVALID`，返回内容未通过应用的输出/完成状态/Schema检查 |
| Vector / Hybrid / RRF | 均未开始 |
| 本轮预留 / 剩余 | 回答5/96、剩91；嵌入1/73、剩72；失败请求也计入 |
| 历史 / 合计 | 旧账本仍84次模型/61次嵌入；加本轮为89/62，分账保留 |
| 裁判 / 人工评分 | 本轮裁判调用0，人工评分覆盖率0% |
| 回答服务上报用量 | 5次均上报：输入6334、输出857 tokens；不含嵌入用量，实际账单金额未知 |

失败请求原始返回未保存，当前错误码不包含具体字段或解析原因，不能认定是引用UUID、结论长度、某个状态字段或网络问题。没有修改问答Schema或提示词来适配测试题，没有重试。四条答案不代表完整测试集，不汇总四组比较、正确率或质量图表；它们也没有模型或人工评分。参考标注为Agent编制，正式图谱来自普通服务的研究审核夹具回放，不代表自动抽取质量或真实个人笔记历史。

## 清理与保存

`run.json` 原样保留，其中 `schema_removed=false` 是旧入口只在整轮成功后设置的标记。失败后另做只读检查，见 [cleanup-verification.json](cleanup-verification.json)：临时 `ka_functional_*` schema剩余0个；实验项目在public中0条；public迁移版本仍 `20261029_0019`。不改原始运行文件来掩盖标记差异。

- [bm25.partial.jsonl](bm25.partial.jsonl)：4条答案、逐条引用、实际输入池及检索元数据；人工字段为空。
- [run.json](run.json)、[preparation.json](preparation.json)：原始运行及隔离项目准备。
- [authorization.json](authorization.json)、[authorization-receipt.json](authorization-receipt.json)、[preflight.json](preflight.json)：授权、请求前预留、历史账本SHA-256和固定方案。
- [summary.json](summary.json)、[artifact-sha256.json](artifact-sha256.json)：部分结果摘要和机器记录指纹。
- [executed-code.json](executed-code.json)：以base64逐字保存运行开始时相对 `02a76bb` 的实现补丁及SHA-256，早于失败后的观测增强。

本轮在 `backend` 执行的命令（仅作记录，同一授权/输出已认领，不得重放）：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_public_acceptance --dataset ../evaluation/holdout-v3 --output-dir ../output/holdout-v3-live-20261031-r1/live --approved-plan ../output/holdout-v3-live-20261031-r1/preflight.json --authorization-ledger ../output/holdout-v3-live-20261031-r1/authorization.json --model-limit 96 --embedding-limit 73 --allow-model-calls --allow-embedding-calls
```

失败后已补充安全错误分类：未来运行记录当前题目、异常类型和Pydantic校验错误类型计数，不保留输入、错误消息或模型正文；不能追溯恢复本次的具体错误。任何新的诊断或重跑仍须明确授权。剩余91/72不意味着自动重试获准；不根据holdout失败调整排序、提示词、阈值或参考答案。本次未准备不完整的裁判包，也未发裁判请求。

## 验证

独立账本聚焦 **33 passed**；完整后端 **941 passed / 11 skipped**。覆盖缺失/变更授权、预算耗尽、锁竞争、计数篡改、重复认领、旧账本不变及成功/失败的完整本地替身流程。最后的脱敏错误观测增强另做聚焦检查 **34 passed**。这些通过项不保证真实模型输出合法。原生数据库准备/清理实际完成，真实问答在上述错误处停止。
