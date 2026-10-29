# Upstream technical notes holdout v3

[简体中文](README.zh-CN.md)

Seven full MIT-licensed FastAPI documentation files, pinned by commit; twenty-four new questions: eight direct, eight cross-document, four temporal and four unanswerable. The source material is real upstream technical documentation, not private user notes. Code include directives remain literal and do not imply included code has been ingested.

Upstream relative links are preserved byte-for-byte and resolve in the pinned upstream tree, not this partial local corpus. They do not imply linked pages were imported.

The previous synthetic v1 and public-v2 sets are development data. All v3 documentation families, including both historical versions, stay in the test split. Do not tune ranking, prompts or thresholds on these questions. The protocol and exact-byte fingerprint are frozen before any provider run. Gold/questions are agent-authored and require independent human review; no human score has been generated.

Historical availability uses the release commit timestamps for 0.94.1 and 0.95.0. Ordinary isolated research review replay replaces the older documentation snapshot, not the API's actual validity. This does not establish real personal-note chronology or a new feature introduction date.

Offline validation from backend: `python -m scripts.prepare_evaluation --dataset ../evaluation/holdout-v3 --validate-only`. No provider run or new answer-quality claim is included. Actual answers and blind review must use a new result directory and the existing cumulative request ledger; the previous 120 model /160 embedding authorization cannot be reset.

The existing 80-row public-v2 blind review is ready at `evaluation/results/2026-10-26-public-v2-run1/blind-review.html`. A real reviewer fills it locally and exports CSV; `scripts.review_public score` imports it into a new directory. Blank correctness/explainability remain missing. The user elected to complete this later.

Split independence is at document/question level. Public-v2 already contains FastAPI code snippets, so upstream framework and some concepts overlap; this is not an unseen-repository or unseen-domain test. Source-family grouping keeps v3 historical versions together, not a claim that all upstream concepts are absent from development data.
