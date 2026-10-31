# Thesis discussion draft and fixed demonstration script

[简体中文](HOLDOUT_DISCUSSION_AND_DEMO.zh-CN.md)

This is a Markdown thesis draft/demo aid, not an edited or finalized Word thesis. Numbers come from the [complete QA retry](../evaluation/results/2026-10-31-holdout-v3-run2/REPORT.md) and [457-request judge report](../evaluation/results/2026-10-31-holdout-v3-clef-run1/REPORT.md). No new model calls are needed.

## Draft experiment discussion

The experiment uses7 pinned public technical documents and24 cases spanning direct facts, cross-document questions, temporal scope and unanswerability. BM25, vector, fixed hybrid andRRF share a curated reviewed graph, index and answer configuration. Retrieval uses exact-source/line/text Evidence Recall@5; automated judging separates correctness, completeness, abstention and per-claim citation support. Human coverage is0%; Agent-authored references are not independent human gold labels.

The four methods yield96 execution records:91 structurally valid exports and5 failures due to inconsistent overall/claim support. Evidence Recall@5 is90.00% for BM25 and97.50% for the others; these are retrieval metrics, not semantic answer accuracy. Clef labels83 of91 valid exports correct. Relative to all96 records,83 carry a correct label, with8 model-incorrect labels and5 output failures separately retained. Per-method totals are24 and graded counts22/24/23/22; conditional percentages must not hide output failures.

On the22 shared valid graded cases, all methods receive20 correct labels. Raw all-case differences do not establish general quality differences; this supplementary validity intersection may have selection bias and neither proves equivalence nor replaces full-case results. Among183 cited claims,103 have high-confidence double-order support and80 are uncertain. All91 abstention judgments are below0.8 confidence. Current evidence supports reporting execution, coverage and traceable failures, but not reliable semantic citation or refusal quality.

Limits include a single model judge, uncalibrated confidence, small related cases, Agent references, curated review replay and no independent human scores. Test/development material shares FastAPI concepts; it is not unseen-domain/repository acceptance. Historical time is document availability/research replay, not API introduction time. Execution changed after an initial failure and one input-verified diagnostic answer is reused; disclose both. Reproduce version/cross-document issues on separate development fixtures and assess changes on a new independent test, without tuning against this holdout.

## Claim boundaries

- Supported statements: shared frozen inputs;96 execution records; explicit failures/missing scores; exact source traceability; reproducible input/configuration fingerprints.
- Unsupported claims:91.21% human/system accuracy, guaranteed entailment, universally best Vector, reliable refusal quality, equivalent extraction quality or full private-repository acceptance.
- If91.21% is quoted, call it the judge's correct-label fraction83/91 on gradable exports, alongside96 total,5 invalid outputs and human coverage0%.

## Fixed offline demonstration, about5 minutes

[demo-cases.json](../evaluation/results/2026-10-31-holdout-v3-clef-run1/demo-cases.json) preserves full answers/citations/labels. Cases are selected illustrations, not representative sampling or independent quality evidence. Temporary experiment schemas are gone; do not imply that the experiment project exists in the application DB. Show saved artifacts rather than generating paid answers live.

| Time | Saved case | Demonstration |
| --- | --- | --- |
| 0:00–0:45 | Four-method table and5 output failures | State96 total,91 graded, human0%; distinguish retrieval from semantic labels |
| 0:45–1:30 | Vector / holdout-v3-01, when background tasks run | Full saved answer, individual claims, exact source lines; Schema validity is not correctness |
| 1:30–2:20 | Vector / holdout-v3-16, heavy background work and request validation | Combine Celery and RequestValidationError evidence from separate sources |
| 2:20–3:10 | Vector / holdout-v3-17, historical2023-03-16 scope | Saved `valid_at`, source version and text; disclose its1 uncertain citation judgment |
| 3:10–3:50 | BM25 / holdout-v3-24, human blind-grading accuracy in documents | Saved refusal/qualification; model grades cannot fill human scores; do not rewrite the saved answer |
| 3:50–5:00 | BM25 / holdout-v3-05 and invalid-output list | A Schema-valid answer can be model-incorrect; show support mismatch failures and80/183 uncertain citations |

## Next work

Freeze this test/run/figures and incorporate the draft into results/limitations. Reproduce version, cross-document evidence and output-contract concerns on separate development material before changing implementations. Formal knowledge still needs human review. Future code/model/deployment work follows its own authorization; this document grants no new calls.
