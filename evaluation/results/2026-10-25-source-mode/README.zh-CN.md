# 可选来源位置 BM25 诊断

[English](README.md)

在既有 40 题/30 份合成开发语料上进行纯检索重放，使用 run.json 记录的相同知识/索引指纹。供应商请求为嵌入 0、回答 0，协议分别为 mixed-bm25-v1 和 mixed-bm25-source-v1。原结果目录保持不变。

| 模式 | 证据 Recall@1 | Recall@3 | Recall@5 |
| --- | --- | --- | --- |
| bm25 | 60.74% | 68.24% | 74.49% |
| bm25_source | 60.05% | 69.17% | 74.49% |

加入文件名/路径/标题改变了排序，但本组 Recall@5 没有提高，Recall@1 略降。因此只作为位置查询的可选入口，不替换默认策略或声称总体提升。该语料已参与开发，不新增人工评分、答案、引用质量估计或独立盲测结论。[另 9 个功能案例](../../regressions/source-location-v1/README.zh-CN.md)也不替代独立真实场景测评。

在 backend 使用 run.json 中的准备项目 UUID 和一个新输出目录复现：

```powershell
python -m scripts.run_evaluation --dataset ../evaluation --project-id <prepared-project-uuid> --output-dir ../output/source-mode-replay --modes bm25 bm25_source
```
