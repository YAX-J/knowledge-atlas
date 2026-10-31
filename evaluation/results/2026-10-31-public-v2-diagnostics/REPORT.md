# Public-v2 historical answer failure analysis

[简体中文](REPORT.zh-CN.md)

Offline analysis of four 2026-10-26 answer exports and their 2026-10-30 Clef anonymous grades: 20 cases per method, 80 answers, and 214 original planned/reserved/completed judge requests. This analysis makes **0** provider requests; human grading coverage remains **0%**. Historical results, raw labels, the 0.8 threshold and holdout-v3 are unchanged.

## Observable gaps

Counts are answers with a corresponding gap, not semantic error rates. The historical pool is the full `retrieved_evidence` export. Top 5 means five evidence records, not five entities. Missing gold citations do not necessarily invalidate alternative supporting citations.

| Method | Gold gap in full pool | Gold gap in first five evidence records | Gold gap in final citations | Model labeled incomplete | Uncertain citation judgments |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 3 | 6 | 4 | 4 | 12 |
| Vector | 4 | 6 | 5 | 4 | 12 |
| Hybrid | 7 | 13 | 8 | 7 | 10 |
| RRF | 3 | 5 | 5 | 4 | 11 |

Representative cases:

| Case | Observation and attribution limit | Next diagnostic |
| --- | --- | --- |
| public-004, required/optional Item fields | All pools omit `tax` at body.py:9, although the curated graph includes that line; answers omit it too | Per-entity evidence clipping before prompt changes |
| public-012, two products and prices | All pools omit the second product at response.py:26 | Later evidence belonging to the same entity |
| public-009, Owner.addVisit | All pools omit `getPet(petId)` at Owner.java:181; Vector/Hybrid also omit line 185 | Entity retrieval versus method-body evidence coverage |
| public-002 / public-014 | Hybrid omits query.py:9; public-002 uses common_parameters' limit 100 instead of query_params' limit 10 | Same-name identifiers and file attribution; no weight fitting on these cases |
| public-013, common required Item fields | All full pools contain the gold evidence, but answers omit the shared `price` field; the exact historical prompt pools were not separately exported | Capture prompt evidence to separate clipping from generation omissions |

Current `app/services/search.py` paths still return `[:3]` evidence records per entity; the public fixture gives these entities 4–5 records. This is consistent with repeated later-line omissions. Current code alone does not establish a unique causal explanation for every historical answer. This round documents the limitation without changing ranking, evidence budgets or prompts; prospective evaluation will include the limitation honestly.

## Judge signals

45 of 67 cited whole-answer units are uncertain, and 75 of 80 abstention judgments have confidence below 0.8. The adapter preserves provider `confidence` and `probabilities` separately; their different values must not be substituted. No local conversion replacing confidence with the selected-label probability was found. No thresholds or raw labels are changed, and neither uncertain nor model-incorrect flags become human error grades.

Correctness and completeness are separate: some public-004 answers are labeled correct but partial. Inspect omissions as well as contradictions. All labels still rely on a single judge and Agent-authored reference facts.

## Artifacts and reproduction

[per-answer.jsonl](per-answer.jsonl) includes all 80 questions/answers, gold evidence, missing locations, raw model labels/confidence and diagnostic flags; every `human_grade` is null. [summary.json](summary.json) records input SHA-256 values, counts and limits. These are development flags, not human grades or established root causes.

From `backend`, use a fresh output directory. Original packet/run inputs remain local under ignored `output/clef-blind-01`; the committed per-answer export is directly readable:

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluation_diagnostics --dataset ../evaluation/public-v2 --predictions ../evaluation/results/2026-10-26-public-v2-run1/bm25.jsonl ../evaluation/results/2026-10-26-public-v2-run1/vector.jsonl ../evaluation/results/2026-10-26-public-v2-run1/hybrid.jsonl ../evaluation/results/2026-10-26-public-v2-run1/rrf.jsonl --packet ../output/clef-blind-01/packet --source-run ../output/clef-blind-01/live/run.json --output ../output/public-v2-diagnostics-new
```

The script checks dataset/packet/run fingerprints, exact citation text and anonymous units, case coverage and exact judge-job coverage. It refuses overwrite and holdout development analysis. See the [current-system experiment plan](../../../docs/CURRENT_SYSTEM_EVALUATION.md).
