# Graduation delivery items 3–8: real model experiment

[简体中文](REPORT.zh-CN.md)

## Scope

On 2026-10-24 the user authorized at most 172 DeepSeek requests using only public synthetic corpus content. The actual `deepseek-flash` run used 112: 10 single-step, 20 tool-loop, 80 answering and 2 extraction requests. All reported numerical usage: 160480 input and 19974 output tokens. Billing cost remains unknown (`null`). No new embeddings were requested. See [acceptance.json](acceptance.json).

Answers replay the frozen version 1.0.1 retrieval evidence, not a new end-to-end online question run. There are 40 questions per mode, 120 outputs. Keyword retrieval found no evidence and refused locally without answer-provider calls. Retrieval searches reviewed formal entities, not raw chunk RAG. These results apply only to this public synthetic corpus.

## Cross-file analysis

All methods share the same candidate generator, with 50 authored cases across ten languages. `candidate_coverage=70%` means the fraction of all cases where any candidate was supplied, not recall of every gold target; negative cases are also in its denominator.

| Metric | Static | Single-step | Tools |
| --- | ---: | ---: | ---: |
| Exact decision accuracy | 62% | 86% | 90% |
| Target precision | 58.62% | 80.95% | 94.12% |
| Target recall | 87.18% | 87.18% | 82.05% |
| Unresolved accuracy | 60% | 80% | 95% |

The tool Agent is more conservative here: better precision but lower recall. It used two provider turns and two or three tools per repository, with higher latency. It cannot discover gold targets absent from the static candidates. One run of 50 cases establishes neither statistical significance nor compiler/runtime semantic correctness.

## Retrieval and answers

| Metric | Keyword | Vector | Fixed hybrid |
| --- | ---: | ---: | ---: |
| Evidence Recall@5 | 0% | 98.06% | 66.02% |
| Automatic support/refusal match | 10% | 100% | 80% |
| Citation F1 | N/A | 81.48% | 68.22% |
| Literal required-fact coverage | 0% | 88.43% | 73.15% |
| Human correctness / explainability | Ungraded | Ungraded | Ungraded |

Whitespace tokenization with AND matching fails on these Chinese questions. The failed keyword baseline is preserved without tuning questions or weights. Vector (graph off) versus fixed hybrid (one-hop graph on) is a limited component ablation: the fixed graph weight worsens retrieval here. It is not a weight search or a fully controlled ranking/candidate ablation, and does not show that graph retrieval is universally ineffective. Automatic answer checks are not human semantic accuracy.

Two extraction samples returned seven entities and six relationships with exact, validated evidence. Semantic correctness and completeness still require actual human review. Extraction acceptance did not promote these outputs into the formal graph.

## Figures and reproduction

[charts](charts/) contains five PNG/SVG pairs: retrieval, call comparison, language breakdown, automatic answer checks and latency. Numerical [values.csv](charts/values.csv) and input [SHA-256 provenance](charts/provenance.json) accompany them. Input hashes use `utf8-lf-v1` (UTF-8 text with normalized LF), avoiding platform-specific CRLF changes; renderer versions are recorded. Missing metrics are N/A, not invented zeros.

From `backend`, install `.[dev,evaluation]`, then render without provider calls:

```powershell
.\.venv\Scripts\python.exe -m scripts.render_experiments --retrieval-dir ..\evaluation\results\2026-10-24-v101\retrieval --acceptance-dir ..\evaluation\results\2026-10-24-models --output-dir ..\output\figures-replay
```

The original paid-run command was `python -m scripts.model_acceptance --dataset ../evaluation --retrieval-dir ../evaluation/results/2026-10-24-v101/retrieval --output-dir ../output/evaluation/model-acceptance-20261024 --allow-model-calls`. A future rerun requires a new output directory, configured provider credentials and renewed user approval; the completed authorization is not an unlimited calling budget.

## Human blind grading remains pending

Give reviewers only [blind-review.csv](blind-review.csv), not `grading-key.json` or the results directory. Rows are shuffled and mode labels hidden, but answer style may still reveal a mode; perfect blinding is not guaranteed. Reviewers fill a pseudonymous `reviewer`, `answer_correct` (true/false) and `explainability_score` (1–5: 1 unverifiable, 3 partly traceable, 5 clearly supported). Correctness checks gold required facts, unsupported claims and appropriate refusals. Scores must be written by actual reviewers; blanks remain missing. Independent double review with recorded disagreement resolution is recommended but not yet performed.

```powershell
.\.venv\Scripts\python.exe -m scripts.import_grades --dataset ..\evaluation --acceptance-dir ..\evaluation\results\2026-10-24-models --review-csv ..\output\reviewed.csv --output-dir ..\output\human-grades
```

Import requires all review IDs exactly once and reviewer identity for filled grades. No model-generated or inferred human scores are supplied. Current human coverage is 0%; cross-document and historical human accuracy are unknown.
