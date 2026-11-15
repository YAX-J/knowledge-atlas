# 结论支持状态 v3 开发验证


这里的四个手写虚构 Nimbus 用例是独立开发夹具，不是冻结质量基准。[cases.json](cases.json) 定义两段来源及四种情况：全部有据、混合支持、全部不足、共享引用。未复制 public-v2/holdout-v3 的语料、题目、失败输出或裁判反馈。预期标志仅表示结构规则，不是模型评分。

新模型协议为 `evidence-claims-v3`，顶层只含 confidence、claims、missing_information，由后端计算总体 supported。模型提供总体标志时，无论是否一致均拒绝；未知/跨项目引用、非法状态、漏引/缺失信息、重复引用、额外字段与长度限制仍严格校验。v2 和平铺历史按保存值读取，不产生新调用。见 [ADR0075](../../../docs/adr/0075-server-derived-answer-support.zh-CN.md)。

使用现有虚拟环境，在 backend 运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_claim_support_v3.py tests/test_answer_claims.py tests/test_questions.py tests/test_conversations.py tests/test_multi_agent.py tests/test_run_evaluation.py tests/test_evaluation_diagnostics.py --basetemp=../output/pytest-claim-v3-focused
```

开发测试用本地 HTTP 替身覆盖 single_step 和 tools，包括拒绝 v2 输出时仅尝试一次。没有真实模型/嵌入/裁判调用。四个正常场景及非法变体只验证软件行为；v3 模型质量和真实格式失败频率仍未测量。历史 v2 实验、失败输出、分母、排除清单、授权和分数保持不变，不重新评分任何数据或协议。

2026-10-31 验证：上述后端聚焦命令通过 118 项，前端结论兼容通过 5 项，生产构建通过。完整后端回归通过 994 项、跳过 11 项。冻结产物不变，未调用真实供应商。人工评分覆盖率仍为 0%。
