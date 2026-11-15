# ADR 0070：Jev 匿名自动评审


- 状态：接受
- 日期：2026-10-30

## 决策

用户选择只用 Jev 做匿名模型评审，不安排人工盲评，取代此前“人工盲评稍后完成”的计划。正式知识候选仍须人工审核。人工评分覆盖率始终为0%，模型结果不写入历史人工评分字段，不声称与人类一致。冻结语料、金标和旧结果保持原样，不得用 holdout 调提示词或阈值。

`scripts.jev_evaluation prepare` 校验数据集、要求每种方法完整导出答案、核对引用精确原文行，打乱匿名评审 ID，并将方法/题目映射另存 grading-key.json。裁判不接收方法名、生成模型身份、原题 ID 或生成置信度。缺少答案时拒绝，不补造答案。旧平铺结果按整答粒度判断，不推断逐条对应；新的公开验收导出包含 claims 及其证据映射。

`scripts.jev_evaluation run` 默认只做零调用预演。真实评估须显式 --allow-jev-calls、配置密钥，并用 --max-requests 覆盖全部计划请求。每次请求先在独占的新输出目录预留并落盘；失败和未知结果也占次数。不自动重试、恢复或覆盖，不从 UI/API/Worker 自动触发。Jev 用量独立于原有 DeepSeek/嵌入账本。本轮用户明确只授权开发和本地验证，真实 Jev 请求为0。

固定 TYPESAFE_MODEL=jev-1.14.0，拒绝别名，校验实际返回模型。backend/.env 添加 TYPESAFE_API_KEY、TYPESAFE_BASE_URL、TYPESAFE_TIMEOUT_SECONDS，密钥留空待用户填写；.env.example 仅含占位。HTTP 输入最多24000字节 UTF-8 JSON、输出最多128 KiB，这是字节保护，不是 tokenizer 估算。不增加 SDK 依赖或隐式重试。

正确性、必需事实覆盖和拒答合理性使用参考事实分别判定；引用支撑请求仅包含一条结论、它实际引用的片段及前后至多三行原文。每条有据结论交换选项顺序各判一次；不一致或置信度低于0.8标为不确定，不视为人工确认。固定阈值只作不确定标记，不代表本项目上已校准的准确率。Jev 返回选项/概率，不生成解释正文。报告记录协议、输入包哈希、模型、预留次数、判定及人工覆盖率0，不证明语义正确。

## 来源与验证

传输遵循官方 [System One API](https://docs.typesafe.ai/api/system-one)、[模型 ID](https://docs.typesafe.ai/models)、[Choice](https://docs.typesafe.ai/primitives/choice) 和[引用核验示例](https://docs.typesafe.ai/cookbooks/citation_check)。官方[已知限制](https://docs.typesafe.ai/model-jaggedness/jev-1.13)说明需限定范围并检查选项顺序，不能据此声称另一版本在本项目上的效果。

测试使用本地 HTTP 替身和临时评审包，覆盖严格传输、大小保护、错误脱敏、缺失/变化输出、精确引文、匿名化、参考事实与引用隔离、调用前落盘及零调用预演。已对冻结的真实 public-v2 BM25 答案导出完成本地准备：20条评审、计划54次请求、实际预留/完成0次、模型/人工评分均0。不宣称质量得分；按用户本轮要求未运行真实评估。
