# Public-v2 历史答案失败分析

[English](REPORT.md)

本报告离线分析 2026-10-26 的四组答案及 2026-10-30 的 Clef 匿名评审：每组 20 题，共 80 条答案；原裁判计划/预留/完成均为 214 次。本次新增供应商请求 **0**，人工评分覆盖率 **0%**。旧结果、裁判原始标签、0.8 阈值和 holdout-v3 均不修改。

## 可复查的观察

下表数字为“存在对应缺口的答案条数”，不是语义错误率。检索池是历史 `retrieved_evidence` 全部条目；Top 5 指其中前五条证据，不是五个实体。引用缺少金标不必然表示引用错误，替代表述也可能有效。

| 方法 | 检索池缺少至少一条金标 | 前五条证据存在缺口 | 最终引用存在金标缺口 | 裁判判不完整 | 引用判断不确定 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 3 | 6 | 4 | 4 | 12 |
| Vector | 4 | 6 | 5 | 4 | 12 |
| Hybrid | 7 | 13 | 8 | 7 | 10 |
| RRF | 3 | 5 | 5 | 4 | 11 |

关键样本：

| 问题 | 观察与归因边界 | 下一步检查 |
| --- | --- | --- |
| public-004，Item 必填/可选字段 | 四组检索池均缺 body.py:9 的 `tax`，答案随之遗漏。正式夹具本来包含该行 | 检查每实体证据裁剪，不能只调回答提示词 |
| public-012，两个商品与价格 | 四组检索池均缺 response.py:26 的第二个商品，答案只覆盖第一个 | 同一实体的后续证据是否被截掉 |
| public-009，Owner.addVisit | 四组均缺 Owner.java:181 的 `getPet(petId)`；Vector/Hybrid 还缺第 185 行 | 区分实体命中与方法体证据覆盖 |
| public-002 / public-014 | Hybrid 缺 query.py:9；public-002 把 common_parameters 的 `limit=100` 用于 query_params 的问题，后者应为 10 | 同名标识符与文件来源混淆；不据本集拟合融合权重 |
| public-013，两个 Item 的共同必填字段 | 四组完整检索池都包含金标，但最终答案漏掉共同的 `price`。历史实际输入池未单独保存 | 需要回答输入池记录，才能区分输入裁剪与生成遗漏 |

当前 `app/services/search.py` 的各检索路径仍把每实体返回证据裁为 `[:3]`，而公开夹具里上述实体有 4–5 条证据。这与重复遗漏后续行的现象一致。历史运行没有完整逐步轨迹，不能仅凭当前代码证明每条历史答案的唯一根因。本轮记录此限制，不改变检索排序、证据预算或回答提示词；正式评估将如实包含当前限制。

## 裁判信号的处理

67 个带引用整答单元中 45 个不确定；拒答合理性 80 条中 75 条置信度低于 0.8。适配器直接保存供应商的 `confidence` 与 `probabilities`，二者数值不同，不能互相替换。未发现本地把所选标签概率误写成 `confidence` 的转换。本轮不下调阈值、不更改原始标签，也不把低置信或“判错”自动写成人工错误标签。

答案正确性与事实完整性是两个维度：public-004 有些回答被判“正确”但“不完整”。失败样本应同时看遗漏与矛盾，而不能只看正确性标签。全部标签仍来自单个模型及 Agent 编制参考事实。

## 交付物与复现

[per-answer.jsonl](per-answer.jsonl) 保存全部 80 条的题目、答案、金标、缺口位置、原始裁判标签/置信度与诊断标记；`human_grade` 均为 null。[summary.json](summary.json) 保存输入 SHA-256、分方法计数及限制。标记是开发诊断，不是人工评分或已证实的因果结论。

在 `backend` 运行，必须选择新的输出目录；原始匿名包及裁判运行保留在本机被忽略的 `output/clef-blind-01`，提交的逐题导出可直接阅读：

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluation_diagnostics --dataset ../evaluation/public-v2 --predictions ../evaluation/results/2026-10-26-public-v2-run1/bm25.jsonl ../evaluation/results/2026-10-26-public-v2-run1/vector.jsonl ../evaluation/results/2026-10-26-public-v2-run1/hybrid.jsonl ../evaluation/results/2026-10-26-public-v2-run1/rrf.jsonl --packet ../output/clef-blind-01/packet --source-run ../output/clef-blind-01/live/run.json --output ../output/public-v2-diagnostics-new
```

脚本检查数据/匿名包/运行指纹、引用原文与匿名单元对应关系、完整题目和评审任务覆盖；拒绝覆盖结果，拒绝将 holdout-v3 用于开发诊断。当前版本端到端实验见[实验方案](../../../docs/CURRENT_SYSTEM_EVALUATION.zh-CN.md)。
