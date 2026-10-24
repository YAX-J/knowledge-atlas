# Synthetic retrieval baselines, 2026-10-24

[简体中文](README.zh-CN.md)

One real-embedding run on native PostgreSQL 17.10 / pgvector 0.8.7. The user authorized embedding calls; DeepSeek answers remain deferred. All modes share one curated graph: 30 sources, 44 entities, 10 semantic relationships, 90 evidence records and one temporal replacement.

| Mode | Recall@1 | Recall@3 | Recall@5 | Mean ms | P95 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Keyword | 0.00% | 0.00% | 0.00% | 7.67 | 22.29 |
| Vector | 50.09% | 87.22% | 98.06% | 218.77 | 238.91 |
| Hybrid | 36.81% | 56.44% | 66.02% | 232.77 | 250.39 |

Recall is macro-averaged over 36 answerable cases; K counts ranked evidence, not entities. Each mode completes 40 cases. Answer/citation correctness, human grading and explainability are unassessed, with zero coverage. Latency includes query embeddings and comes from one sequential run, without repeated trials or significance claims.

- Dataset `knowledge-atlas-eval-v1` / `1.0.1`: `bc4b27b3ff83f68063f88223b37b22ac526e29f4cc6f5418620dab1267889563`
- Annotations `pulseboard-curated-graph-v1` / `1.0.0`: `41f4e8a7ae861a4fad1926c50de1415e0c45d9cafd4ef4af9c350b19d245ca39`
- Actual knowledge: `07cb0d81ebd417ef30563b9413208d79480104a60ca821e0b5399dcb3ca267f5`
- Actual index: `48df73ab4580e169fc19ad763fa409b75503c6324c8ab6925b6b17db253fd650`
- Model `qwen3.7-text-embedding-flash`, 1024 dimensions, index batch size 10; scoring `line-evidence-v2`.
- Top K entities=5; hybrid weights=0.3/0.4/0.3.

Keyword retrieval splits on whitespace and requires every term; long Chinese clauses generally fail substring matching. This is not a competitive Chinese-tokenized/BM25 baseline. Hybrid underperforms vector despite 182 positive graph-score hits: nonzero signals do not guarantee correct ranking. Graph-induced reranking is a hypothesis for ablation, not proof that graph retrieval is generally ineffective. The vector group indexes reviewed entities rather than all raw chunks as in conventional chunk RAG. The curated synthetic inputs omit extraction noise and do not establish real-repository generalization.

This directory retains 120 predictions, 120 diagnostics, metrics, manifests and CSV comparisons without credentials, URLs, vectors or raw provider responses. The successful run made 85 successful embedding calls, zero failures and zero answer calls; billing tokens/cost are unknown. An earlier 32-text index request failed, followed by one successful single-text embedding diagnostic and a read-only model-list request. The first failed report remains locally under `output/evaluation/baselines-20261024-v101/`. Total embeddings this round: 86 successful, one failed.

Rescore offline from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_dataset score --dataset ..\evaluation --predictions ..\evaluation\results\2026-10-24-v101\retrieval\vector.jsonl
```

For a new run, follow [the instructions](../../README.md), use new project/output directories and confirm provider-call authorization.
