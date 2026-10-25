# 2026-10-25: provider-free BM25 development diagnostic

[简体中文](README.zh-CN.md)

The [run manifest](run.json), complete predictions, per-case diagnostics and metrics are retained here. Dataset 1.0.1 has 40 questions (36 answerable); corpus, actual graph and index fingerprints exactly match the 2026-10-24 baseline. This run reads the existing public synthetic project without business/index writes. Answer and embedding requests are both zero. Answer accuracy, human grades and explainability remain null.

## Same-run comparison

| Evidence metric | Literal keyword | mixed-bm25-v1 |
| --- | ---: | ---: |
| Recall@1 | 0% | 60.74% |
| Recall@3 | 0% | 68.24% |
| Recall@5 | 0% | 74.49% |

BM25 mean latency was 20.84 ms, P95 21.84 ms, for this small local run only, not a load test. Comparing provider latency across dates cannot establish general performance gains. The unchanged `line-evidence-v2` scoring expands hit entities into evidence, then scores the first K evidence records, not K entities.

## Limitations retained

| Category | Questions | Recall@5 |
| --- | ---: | ---: |
| Direct fact | 16 | 100% |
| Cross-document | 8 | 60.21% |
| Code location | 6 | 0% |
| Temporal | 6 | 100% |

Incomplete coverage: `cross-001/002/004/005/007/008` and every `code-001..006`. Natural-language-to-code queries without lexical overlap still need semantic retrieval; related Chinese documents may outrank code. Different entities citing identical source text also occupy multiple evidence positions. The existing scoring protocol was not changed to favor the new method.

All four unanswerable questions returned lexical matches. This is not answer correctness: retrieval hits do not establish answerability. Scores are uncalibrated; no post-hoc threshold hides these failures. No answers were generated.

These public synthetic questions have already informed development, so this is a **development diagnostic**, not blind/held-out evaluation or proof of generalization. Parameters were not learned from gold answers. Next steps require independent questions/repositories, controlled fusion ablations and actual human review.

## Reproduction

From `backend`, substitute the prepared project's UUID and a new output directory:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_evaluation --dataset ..\evaluation --project-id YOUR_EVAL_PROJECT_UUID --output-dir ..\output\evaluation\bm25-replay --modes keyword bm25 --top-k 5
```

Do not add `--allow-embedding-calls` or `--with-answers`; no provider credentials are needed. The runner checks source/graph fingerprints and rejects external sources or in-run drift. Tokenization and resource limits: [ADR 0044](../../../docs/adr/0044-bounded-offline-bm25-search.md). Prior vector/hybrid/answer experiments remain untouched and incur no new cost.
