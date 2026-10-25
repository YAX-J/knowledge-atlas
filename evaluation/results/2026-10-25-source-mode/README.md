# Optional source-aware BM25 diagnostic

[简体中文](README.zh-CN.md)

Retrieval-only replay of the existing 40-question / 30-source synthetic development corpus, with the same knowledge/index fingerprints recorded in run.json. Provider requests: 0 embedding, 0 answer. Protocols: `mixed-bm25-v1` and `mixed-bm25-source-v1`; original result directories remain unchanged.

| Mode | Evidence Recall@1 | Recall@3 | Recall@5 |
| --- | --- | --- | --- |
| bm25 | 60.74% | 68.24% | 74.49% |
| bm25_source | 60.05% | 69.17% | 74.49% |

Adding filename/path/heading text changes ranking without improving overall Recall@5 here and slightly lowers Recall@1. Keep the new mode optional for location-oriented queries; do not replace defaults or claim general improvement. This corpus has already informed development. No human scores, answers, citation-quality estimates or held-out claims are added. The [nine separate functional cases](../../regressions/source-location-v1/README.md) are not a replacement for independent real-world evaluation.

Reproduce from backend with the prepared project UUID in run.json and a new output directory:

```powershell
python -m scripts.run_evaluation --dataset ../evaluation --project-id <prepared-project-uuid> --output-dir ../output/source-mode-replay --modes bm25 bm25_source
```
