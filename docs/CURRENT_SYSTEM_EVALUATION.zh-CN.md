# 当前版本问答的端到端实验

[English](CURRENT_SYSTEM_EVALUATION.md)

2026-10-31：已完成[历史失败分析](../evaluation/results/2026-10-31-public-v2-diagnostics/REPORT.zh-CN.md)，并补齐当前在线验收入口。以下是前瞻实验方案，**尚未进行真实 holdout-v3 问答或裁判调用**。本轮新增真实请求为 0；人工评分覆盖率仍为 0%。实验口径已记录，调用预算仍待单独授权。

本机零调用配置、指纹和预算拦截记录见 [preflight.json](../evaluation/experiments/2026-10-31-current-system-v3/preflight.json)。该记录未消耗授权，也不是预算批准文件。

## 固定方案

| 项目 | 约定 |
| --- | --- |
| 开发 / 测试 | v1/public-v2 仅开发诊断；holdout-v3 独立测试，不据其结果调排序、提示词、裁判或阈值 |
| 数据 | 原有 7 份固定提交公开文档、24 题：8 直接、8 跨文档、4 历史、4 无答案；字节和参考标注均不修改 |
| 模式 | BM25、Vector、Hybrid、RRF，各 24 题；相同已审核夹具图谱、向量索引、回答模型及配置 |
| 在线入口 | `questions.answer_question`，`single_step`，5 个实体、最多 12 条回答输入证据；`evidence-claims-v2` |
| 时间 | 每题实际传入 `case.valid_at`；历史问题不使用当前时间；按该时间检查向量覆盖 |
| 主指标 | 沿用 `line-evidence-v2` 的宏平均 evidence Recall@5；这里 K 指导出顺序前五条证据 |
| 补充指标 | 引用 F1、原始模型正确性/完整性/拒答标签、低置信比例、逐条结论双序支持与不确定比例、时延、请求/供应商上报用量 |
| 分类 | 直接/跨文档/历史/无答案分别汇总；有据结论引用支持率以带引用结论为分母，无引用/证据不足另报 |
| 统计解释 | 保留逐题配对结果与差值区间，小样本、不独立题目、单轮网络时延均不证明普遍优势或容量 |
| 不修改的限制 | 当前检索每实体只返回最多 3 条证据；结构校验不证明语义蕴含；图谱来自 Agent 编制夹具的审核回放，不证明自动抽取质量 |
| 模型裁判 | 建议沿用已跑通的 CF `@cf/cloudflare/clef` decision 协议及 0.8 不确定阈值，不按 holdout 分数换裁判；无不可变权重版本须披露。真实运行前核对预演配置并单独授权 |

正式知识写入仍须人工审核。模型评审不得填人工 `answer_correct` / `explainability_score`。历史实验不回填结论归属，新输出单独保存。

## 入口改动

`scripts.run_public_acceptance` 现在支持 public-v2 和 holdout-v3；后者不执行只属于 public-v2 的两份代码抽取冒烟。`--preflight` 无需密钥、不连接数据库、不请求供应商；加载冻结数据及夹具、计算预算并只读历史账本。

预演记录回答/嵌入模型、维度、批次、数据/夹具/协议及应用代码指纹。holdout 的真实入口还要求 `--approved-plan <run.json>`，与即时重算方案完全一致；输入、代码、模型或账本变化须重新预演。预演文件不是调用授权。

新 `online-claims-export-v1` 输出逐题时间、结论、结论引用映射、实际回答输入池和检索元数据。冻结旧评分器只接收兼容投影 `<mode>.metrics-input.jsonl`；丰富的 `<mode>.jsonl` 供匿名裁判准备使用。两者不混用，未修改冻结 prediction schema。部分结果、调用前预留、错误停止、无重试/恢复/覆盖等规则保留。

## 零调用预演和预算

在 `backend` 执行，每次换新目录：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_public_acceptance --dataset ../evaluation/holdout-v3 --output-dir ../output/holdout-v3-new/preflight --model-limit 96 --embedding-limit 73 --preflight
```

本机批次 32、19 个夹具实体的预演上限：

| 类别 | 本轮上限 | 历史已预留 / 原上限 | 历史余额 |
| --- | ---: | ---: | ---: |
| 回答模型 | 96（24×4；本地无证据拒答可能减少） | 84 / 120 | 36 |
| 嵌入 | 73（1 次建索引 + 24×3 查询） | 61 / 160 | 99 |
| 裁判 | 答案导出后按真实有据结论数预演 | 旧 Clef 214 次是独立历史记录 | 不从旧授权推断 |

因此当前预演 `status=prepared`、预留/完成均为 0，并报告回答预算缺口；真实入口在连接数据库和请求供应商前拒绝运行。不能增加目录或把历史用量重置为 0 来绕过。若决定执行完整四组实验，需要用户明确授权新的回答预算，并保留旧账本、记录新授权后重新预演。嵌入虽有余额，本轮真实使用也需明确授权。裁判请求为每答 `1 + 2×有引用的支持结论数`，96 答最多 1632 次；这只是结构上限，须待实际导出后确定精确次数并单独授权，不预先执行。

后续真实命令的形状如下，**现有授权下会被拒绝**；预算处理及新预演完成前不要执行：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_public_acceptance --dataset ../evaluation/holdout-v3 --output-dir ../output/holdout-v3-new/live --approved-plan ../output/holdout-v3-new/preflight/run.json --model-limit 96 --embedding-limit 73 --allow-model-calls --allow-embedding-calls
```

## 论文与演示产出

真实运行后再生成分方法/分类表、失败案例与图表；当前不编造新版分数。论文分别写明检索评价、模型自动评价、人工覆盖率 0%、公开文档/模拟历史/已审核夹具边界。答辩准备普通事实、跨文档、历史截面和无证据拒答四类固定案例，并提前保存结果，避免现场重复付费；holdout 观察到的问题留待后续独立开发集处理。

## 本轮验证

用户选择由 Agent 执行离线验证。聚焦测试覆盖指纹/匿名映射/原文、输入不变、完整 96 条当前 QA 导出的 SQLite/本地供应商替身流程、历史时间、调用前账本预留、失败不重试、预算及批准方案拦截；替身结果只用于工程验证，不作为 holdout 质量分数。聚焦组合 **115 passed**，完整后端 **931 passed / 11 skipped**，最终预演元数据补测 **19 passed**；`git diff --check`、双语链接和历史输入 SHA-256 核对通过，原账本仍84/61。

首轮沙箱内检查因 pytest 临时目录权限及 TestClient 停滞中止，随后使用同一虚拟环境、项目 `output` 下明确的新 `--basetemp`，在获准的沙箱外执行上述通过的测试。完整命令为 ` .\.venv\Scripts\python.exe -m pytest --basetemp=../output/pytest-evaluation-full-20261031 --tb=short`（在 `backend`）。没有新增界面或数据库结构，不需要前端构建/浏览器走查；本轮未运行原生 PostgreSQL 完整真实实验。
