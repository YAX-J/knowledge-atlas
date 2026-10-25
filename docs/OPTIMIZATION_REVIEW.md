# Graduation-project optimization review (2026-10-25)

[简体中文](OPTIMIZATION_REVIEW.zh-CN.md)

## Assessment and selected scope

The project already closes the source → exact evidence → extraction candidates → human review → formal temporal graph → retrieval → grounded question loop, with a separate multilingual tool Agent, synthetic evaluation, CI definition and local demo. This round prioritizes retrieval effectiveness, experimental credibility and bounded operation; it is not a guarantee of any institution's graduation requirements.

| Area | Evidence | This round |
| --- | --- | --- |
| Chinese retrieval | Literal keyword Recall@5 was zero on 40 frozen questions | Add a separate provider-free BM25 mode; preserve defaults and old results |
| Cost and empty states | Query embedding preceded index availability checks | Validate configuration locally and skip embedding when no matching index exists |
| Explainability/bounds | Ranking scores can be mistaken for confidence; truncation can mean incomplete scans | Return terms, scan counts and truncation reasons; distinguish lexical scans from vector indexes |
| Interaction reliability | The submit function relied on disabled buttons rather than a busy guard | Guard form submission and add component regressions; preserve App request fencing |
| Research integrity | The 40 questions informed development; human grades remain empty | Freeze a separate diagnostic with category failures, not a held-out or human-quality claim |

## Implemented changes

1. `services/lexical.py` implements dependency-free mixed-language tokenization and Okapi BM25, protocol `mixed-bm25-v1`. Han characters/bigrams and Unicode identifiers/parts require no gold-answer input. Counters retain query terms only, while all tokens still contribute to length normalization; a second provider-free replay reproduced all 80 archived predictions/diagnostics except measured latency. Formula and fixed parameters: [ADR 0044](adr/0044-bounded-offline-bm25-search.md).
2. `/projects/{id}/search?mode=bm25` reads only user/project/type/time-visible formal entities and scoped evidence: 1000 entities, 5000 ranking evidence rows, 2000 characters per quote and 4000 ranking characters per entity. Existing UUIDs, exact evidence and source links are retained; no migration or model call is added.
3. Semantic retrieval skips query embedding for empty matching indexes, preserving configuration/dimension errors and indexed behavior. Hybrid can still use its literal/graph branches; provider failures are not silently ignored.
4. The UI adds “BM25 · 无需模型”, scan/truncation explanations and a warning that scores are not confidence. Empty lexical results do not incorrectly suggest building vector indexes; busy form submissions are blocked.
5. The runner supports provider-free BM25 experiments, records protocols/diagnostics and rejects empty/unsupported mode lists. Predictions, metrics and manifest: [new experiment](../evaluation/results/2026-10-25-bm25/README.md). Parsing, review/promotion, fixed hybrid weights and online questions remain unchanged.

## Results and tradeoffs

On the same 40 questions and identical corpus/actual graph/index fingerprints, BM25 evidence Recall@1/3/5 is 60.74% / 68.24% / 74.49%; literal keyword remains zero. Provider requests are zero. This adds an offline Chinese search option, not a replacement for semantic retrieval.

Failures are retained: code-location Recall@5 is zero across six cases; cross-document recall is 60.21%. All four unanswerable questions still retrieve lexical matches, which do not establish answerability. Different entities citing the same text also occupy multiple evidence positions. Scoring and thresholds were not changed to hide these weaknesses.

No repeated hybrid weight tuning on the same questions, new paid calls or retrospective changes to historical reports were performed. New results are development diagnostics, not held-out or end-to-end answer-quality evidence.

## Next priorities, not silently implemented

1. **Independent data and actual human grades**: real reviewers complete the blind packet; add unseen Chinese questions and repositories, including multi-hop, misleading evidence, abstention and code locations. Never infer missing human grades.
2. **Controlled fusion experiments**: compare BM25/vector/fixed hybrid, RRF or bounded graph boosts on independent questions. Define metrics, evidence deduplication and development/test splits before selection; current results do not justify changing default weights.
3. **Agent candidate coverage**: five constructed cases per language cannot establish language-wide quality. Evaluate build-context coverage separately from model decision errors; do not promise a full runtime call graph.
4. **Orchestration tests and maintainability**: `App.vue` is currently 1290 lines. Add App-level project-switch/cancellation/late-response tests before extracting import/graph/search composables. This round preserves orchestration rather than rewriting it concurrently.
5. **Recoverability and environment acceptance**: run hosted CI/container builds where available and rehearse database backup/restore. Authentication/rate limits/secret deployment require a separate public-hosting design; this remains a local single-user application and is not published.

Scoped component coverage near 50% is not full-site end-to-end coverage. Human grading, Docker/hosted CI and representative private-repository model quality remain separate pending work.

## Verification

The user selected Agent execution; no new model/embedding calls were made.

- Focused backend: `python -m pytest tests/test_lexical_search.py tests/test_search.py tests/test_run_evaluation.py tests/test_questions.py --tb=short --show-capture=no`: 43 passed.
- Full backend: `python -m pytest --cov=app --cov-fail-under=90 --cov-report=term --cov-report=xml:../output/backend-coverage.xml`: 605 passed, 5 opt-in checks skipped, application statement coverage 94.37%; one existing Starlette/httpx deprecation warning.
- `python -m scripts.verify_native`: native PostgreSQL 17.10 / pgvector 0.8.7 disposable-schema migration/contention/leases/initialization and new lexical checks passed; schema removed and application migration marker unchanged.
- Frontend `npm run test:coverage`: strict source/test type checks and 18 tests passed; scoped client/four-component statements 50%, branches 48.62%. `npm run build` passed.
- System Chrome at 1440×1100: real BM25 input/keyboard submit/evidence, empty results, validation errors and retry; delayed local response did not overwrite cleared state. Visible focus, independent result scrolling, no horizontal overflow or page errors. Search-region axe: zero automatic violations, one contrast check incomplete due to scrolling occlusion, not comprehensive accessibility certification.
- `git diff --check` and local documentation links passed. Credentials, dependencies and local screenshots are not tracked; experimental artifacts contain public synthetic content only.
