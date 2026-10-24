# Knowledge Atlas 测评集

[English](README.md)

本目录提供阶段六实验共用的冻结测评集。它把测试语料、问题、标准答案和可逐字核验的标准证据一起纳入版本控制，使关键词、向量 RAG 和知识图谱混合检索使用相同的输入和评分口径。测评集不调用外部模型，也不代表真实 DeepSeek 或嵌入服务已经完成质量验收。

## 数据集范围

- 30 个完全合成、无隐私信息的来源：20 篇项目文档、6 个多语言代码文件、4 条 Git 活动记录。
- 40 个中文问题：16 个直接事实题、8 个跨文档题、6 个代码定位题、6 个时序题、4 个不可回答题。
- 每个可回答问题包含标准答案、必要事实、期望实体或关系，以及文件、行号和逐字引用组成的标准证据。
- 不可回答题不附带标准证据，用于检查系统是否拒绝无依据回答。

该规模用于可复现的第一版实验，不代表真实中型仓库的最终外部效度。真实公开仓库、30 至 50 篇个人技术笔记和真实模型质量仍应作为单独实验记录，不能与这套合成集混报。

## 文件结构

```text
evaluation/
├─ manifest.json            # 版本、数量和类别分布
├─ case.schema.json         # 单条金标准问题的 JSON Schema
├─ prediction.schema.json   # 单条预测记录的 JSON Schema
├─ cases.jsonl              # 40 条问题、答案和证据
└─ corpus/
   ├─ docs/                 # 项目文档
   ├─ code/                 # Python、TypeScript、Java 和 Go 代码
   └─ git/                  # Commit、Issue、PR 与 Review 记录
```

`fingerprint_sha256` 由清单、问题和全部语料内容共同计算。任何问题、证据行号或语料变化都会产生新的指纹；正式实验报告必须记录数据集版本和指纹。

## 校验金标准

从 `backend/` 运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_dataset validate --dataset ..\evaluation
```

校验器会检查：

- 来源数、问题数和类别分布与 `manifest.json` 一致；
- 问题 ID 唯一，字段、时区、关系类型和可回答状态合法；
- 每条标准证据都位于数据集目录内；
- `start_line`、`end_line` 和 `quote` 与 UTF-8 原文件逐字一致；
- 可回答题必须有必要事实和证据，不可回答题不得伪造证据。

成功时输出数据集摘要和 SHA-256 指纹。该命令不访问网络、数据库或模型。

## 准备实验项目

每个实验组应使用独立的空项目和相同语料，避免已有知识影响结果。

1. 按 `corpus/` 下的相对路径上传全部 30 个来源并完成解析。
2. 对三组实验使用同一份人工确认的正式实体、关系、证据和时序替代记录。模型抽取结果不能未经审核直接作为金标准。
3. 关键词组不构建向量；向量 RAG 与混合组使用相同嵌入模型、维度和索引快照。
4. 时序题必须按 `cases.jsonl` 的 `valid_at` 发起查询。
5. 每次运行保存模式、模型名称、参数、开始时间、数据集版本和指纹。密钥、完整模型响应及私有内容不得写入结果。

本目录暂不提供自动写入正式图谱的夹具加载器，因为正式知识必须经过审核。可以通过现有界面或 API 完成导入、抽取和确认；三组实验准备完成后再批量记录预测。

## 运行三组实验

实验运行器只读取已经准备好的隔离项目，不导入资料、不写正式知识，也不覆盖已有输出目录。默认命令只执行关键词检索，不访问模型或嵌入服务：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_evaluation `
  --dataset ..\evaluation `
  --project-id <项目 UUID> `
  --output-dir ..\output\evaluation\keyword-run
```

向量和混合模式会为每个问题调用嵌入服务，因此必须显式授权：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_evaluation `
  --dataset ..\evaluation `
  --project-id <项目 UUID> `
  --output-dir ..\output\evaluation\retrieval-run `
  --modes keyword vector hybrid `
  --allow-embedding-calls
```

只有再添加 `--with-answers` 才会在存在检索证据时调用 DeepSeek。一次三模式回答实验最多产生 80 次查询嵌入调用和 120 次回答调用；无证据问题不会调用回答模型。建议先分别完成三组纯检索实验，确认成本和结果后再开启回答实验。

运行前会强制检查项目恰好包含语料中的 30 个来源、文件名和 SHA-256 完全一致、全部解析为 `ready`；向量和混合模式还要求所有可见正式实体都已建立索引。任一检索证据指向语料外来源时运行失败。每次运行创建新的输出目录，并保存：

- `run.json`：数据集版本/指纹、项目、模式、Top K、模型名称、显式供应商授权、成功完成的供应商调用次数和运行状态；
- `<mode>.jsonl`：完整预测记录；
- `<mode>.metrics.json`：该模式的即时评分；
- `<mode>.partial.jsonl`：仅在中途失败时保留的已完成样本。

运行清单不会保存密钥、数据库地址或完整供应商响应。`latency_ms` 在纯检索运行中表示检索耗时；开启回答时表示检索与回答的总耗时。

## 预测文件

评分输入是 JSONL，每个问题恰好一条记录，字段见 `prediction.schema.json`：

```json
{"id":"direct-003","retrieved_evidence":[{"source":"corpus/docs/07_upload_limits.md","start_line":5,"end_line":5,"quote":"一次文件夹或 GitHub 快照最多选择 50 个支持文件。"}],"citations":[{"source":"corpus/docs/07_upload_limits.md","start_line":5,"end_line":5,"quote":"一次文件夹或 GitHub 快照最多选择 50 个支持文件。"}],"answer":"一次最多选择 50 个支持文件。","supported":true,"latency_ms":183.4,"answer_correct":true,"explainability_score":5}
```

- `retrieved_evidence` 按检索排序填写，用于计算 Recall@K。
- `citations` 只填写最终答案实际引用的证据。
- `source` 使用本目录中的相对路径；API 返回标题时，需要按唯一文件名映射回该路径。
- 纯检索运行把 `answer` 和 `supported` 设为 `null`，答案与引用指标显示为未评测而不是错误。
- `answer_correct` 由人工按下述规则填写；未完成复核时填 `null` 或省略，评分器不会把它猜成正确。
- `explainability_score` 是 1 至 5 的人工评分；未评分时填 `null` 或省略。

## 人工评分规则

`answer_correct` 只有在以下条件全部满足时才标为 `true`：

1. 回答覆盖该问题列出的全部 `required_facts`；
2. 没有与语料冲突的附加断言；
3. 时序题使用正确的时间截面；
4. 不可回答题明确拒答，没有补造事实。

可解释性评分采用统一五级量表：

| 分数 | 判定 |
| --- | --- |
| 1 | 无引用或无法定位来源 |
| 2 | 有引用，但与主要结论关系不清 |
| 3 | 主要结论可追溯，仍需人工推断 |
| 4 | 结论与证据对应清楚，文件和行号可核验 |
| 5 | 证据完整、定位准确，并清楚解释跨文档或时间关系 |

建议由同一名评审者完成三组盲评，或由两名评审者独立评分后记录分歧处理方式。

## 计算指标

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_dataset score `
  --dataset ..\evaluation `
  --predictions ..\output\evaluation\hybrid.jsonl `
  --output ..\output\evaluation\hybrid.metrics.json
```

评分器输出：

- 标准证据的宏平均 Recall@1、Recall@3、Recall@5；
- 引用精确率、召回率、F1 和答案评测覆盖率；
- 可回答或拒答判断准确率；
- 必要事实覆盖率；
- 人工答案正确率及人工评分覆盖率；
- 跨文档题正确率和历史追溯题正确率；
- 平均延迟与 P95 延迟；
- 平均可解释性评分及评分覆盖率。

评分器要求预测文件覆盖全部 40 个问题，防止通过漏交困难样本抬高结果。纯检索文件的答案指标为 `null` 且覆盖率为 0；必要事实覆盖率只是确定性辅助指标，不能替代人工答案正确率。
