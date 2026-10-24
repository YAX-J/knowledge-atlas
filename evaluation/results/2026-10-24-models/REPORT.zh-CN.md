# 毕业设计第 3—8 项交付：真实模型实验

[English](REPORT.md)

## 实验边界

2026-10-24，用户授权最多 172 次 DeepSeek 请求，只发送仓库公开合成语料。实际 `deepseek-flash` 请求 112 次：单轮 Agent 10 次、工具 Agent 20 次、回答 80 次、抽取 2 次；全部返回数值用量，共输入 160480、输出 19974 tokens。费用未知，保持 `null`。本轮不重新请求嵌入服务。详见 [acceptance.json](acceptance.json)。

回答使用已冻结 `1.0.1` 检索结果的证据重放，不是再次运行在线问答链路；每种模式 40 题，共 120 条回答，其中关键词模式无证据，直接本地拒答，故没有回答模型请求。检索来自审核后的正式实体，不是原始分块 RAG。该运行只能证明这些公开合成样例的行为。

## 跨文件调用

50 道金标、10 种语言、共用同一候选生成器。`candidate_coverage=70%` 是全部案例中存在任意候选的比例，分母也含负例，不是每个金标目标都被召回的比例。

| 指标 | 静态候选规则 | 单轮模型 | 工具 Agent |
| --- | ---: | ---: | ---: |
| 精确判定准确率 | 62% | 86% | 90% |
| 目标精确率 | 58.62% | 80.95% | 94.12% |
| 目标召回率 | 87.18% | 87.18% | 82.05% |
| 未知调用判定正确率 | 60% | 80% | 95% |

工具 Agent 在本次样例上更保守，精确率提高但召回下降；每个仓库实际 2 次模型请求、2—3 次工具调用，明显慢于单轮。它不能补全静态候选外的真实目标。50 题仅运行一次，不能声称统计显著提升或通用编译/运行时语义正确。

## 检索与回答

| 指标 | 关键词 | 向量 | 固定权重混合 |
| --- | ---: | ---: | ---: |
| 检索证据 Recall@5 | 0% | 98.06% | 66.02% |
| 支持/拒答自动判定 | 10% | 100% | 80% |
| 引用 F1 | 无可评引用 | 81.48% | 68.22% |
| 必要事实字面覆盖 | 0% | 88.43% | 73.15% |
| 人工正确率 / 可解释性 | 未评分 | 未评分 | 未评分 |

关键词基线对中文问题按空白切分、全部词 AND 匹配，导致零召回。保留失败结果，不临时修改问题或调参。向量（移除图关系）与固定混合（加入一跳图关系）构成当前有限的组件消融：在该语料、该候选范围下，固定图权重降低了检索效果。它不是独立权重搜索，也未控制所有排序/候选差异，不据此推断图检索普遍无效。回答自动检查不等于人工语义正确率。

两份抽取样例共返回 7 个实体、6 条关系，所有证据均通过原文逐字检查；语义完整性与正确性仍待真实人工审核。未将抽取验收结果自动写入正式图谱。

## 图表与复现

[charts](charts/) 提供 5 组 PNG/SVG：[检索](charts/retrieval.png)、[Agent 对比](charts/calls.png)、[语言分项](charts/languages.png)、[回答自动指标](charts/answers.png)、[耗时](charts/latency.png)。[values.csv](charts/values.csv) 保存数值，[provenance.json](charts/provenance.json) 保存输入 SHA-256：使用 `utf8-lf-v1`，对 UTF-8 文本统一 LF 换行后计算，避免平台 CRLF 差异，并记录绘图库版本。缺失分数画为 N/A，不冒充零。

在 `backend` 安装 `.[dev,evaluation]` 后，无模型调用重绘：

```powershell
.\.venv\Scripts\python.exe -m scripts.render_experiments --retrieval-dir ..\evaluation\results\2026-10-24-v101\retrieval --acceptance-dir ..\evaluation\results\2026-10-24-models --output-dir ..\output\figures-replay
```

原付费运行命令为 `python -m scripts.model_acceptance --dataset ../evaluation --retrieval-dir ../evaluation/results/2026-10-24-v101/retrieval --output-dir ../output/evaluation/model-acceptance-20261024 --allow-model-calls`。未来重跑要使用全新目录、配置供应商凭据并重新获得用户授权；本轮完成的授权不是无限调用预算。

## 人工盲评：尚未完成

向真实评审单独分发 [blind-review.csv](blind-review.csv)，不要分发 `grading-key.json` 或结果目录。CSV 已随机打乱并隐藏模式，但答案风格可能间接暴露模式，不能保证完全盲法。评审填写匿名 `reviewer`、`answer_correct`（true/false）和 `explainability_score`（1—5）；1 表示依据不可核验，3 表示部分可追溯，5 表示论点与引用清晰吻合。正确性同时检查金标必要事实、不编造和合理拒答。真实评审自行填写，空项保持缺失；建议独立双人评分并记录分歧处理，本轮尚未实施。

```powershell
.\.venv\Scripts\python.exe -m scripts.import_grades --dataset ..\evaluation --acceptance-dir ..\evaluation\results\2026-10-24-models --review-csv ..\output\reviewed.csv --output-dir ..\output\human-grades
```

导入必须覆盖全部盲评 ID 且不重复；填分必须填评审匿名标识。不会把空白变成模型推测的分数。当前人工覆盖率为 0%，跨文档/历史回答人工准确率也没有结论。
