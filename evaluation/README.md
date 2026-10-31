# Knowledge Atlas Evaluation Set

Latest retry: [96 records,91 valid/5 invalid](results/2026-10-31-holdout-v3-run2/REPORT.md) completed under explicit ADR0074 isolation, without online Schema/prompt/ranking changes. One diagnostic reuse is disclosed. Retry usage96 model/73 embedding includes diagnostic; old ledgers unchanged. Judge coverage91/96 and zero-call CF Clef plan457; live judging unauthorized, human grades0%.

Earlier failed attempt: the [first authorized live holdout-v3 attempt](results/2026-10-31-holdout-v3-run1/REPORT.md) stopped on answer5 with invalid output, saving4 BM25 answers. Separate grant usage5 model/1 embedding; no retry or judging, no complete comparison. Historical84/61 remains unchanged.

Earlier preparation checkpoint, before live authorization: [80-answer historical failure analysis](results/2026-10-31-public-v2-diagnostics/REPORT.md) used no new provider calls. The [current online entry](../docs/CURRENT_SYSTEM_EVALUATION.md) planned96 model/73 embedding requests but the old authorization was insufficient. The later independently authorized partial live attempt is recorded above; human grades remain absent.

Optional `--modes rrf` requires `--allow-embedding-calls`, records `bm25-vector-rrf-v1` plus rank diagnostics. Frozen results and `line-evidence-v2` remain unchanged. The runner retains historical evidence expansion/answer replay; it does not evaluate the new online deduplication pipeline end to end. No new provider experiment was run.

[简体中文](README.zh-CN.md)

The new [provider-free BM25 development diagnostic](results/2026-10-25-bm25/README.md) uses the same frozen corpus/graph/index without overwriting prior runs. Use `scripts.run_evaluation --modes keyword bm25` without provider flags. BM25 Recall@5 is 74.49% here, but code-location recall is zero and unanswerable queries still retrieve text; this is not held-out or answer-quality acceptance.

Current delivery also includes a separate [ten-language call gold set](calls/README.md), [112-request real model acceptance](results/2026-10-24-models/REPORT.md), frozen-evidence answer replay, five reproducible charts and a blind grading CSV. Actual human grades remain pending. Retrieval-only results and answer replay must not be conflated with live end-to-end answer accuracy.

This directory contains the frozen evaluation set shared by the Stage 6 experiments. It versions corpus, questions, gold answers and line-exact evidence so keyword, formal-entity vector and knowledge-graph hybrid retrieval share inputs and scoring rules. This is not raw chunk RAG. Dataset validation itself makes no provider calls; real runs and their limited quality conclusions are recorded separately above.

Dataset `1.0.1` fixes time leakage in `temporal-006`: its June 16 query formerly cited a July 18 policy. It now asks only about historical notes retained by the available commit. Do not mix version `1.0.0` fingerprints or scores with this version. Scoring protocol `line-evidence-v2` matches files, inclusive lines and interior text, allowing the outer whitespace trimming performed by the formal evidence schema. Gold source lines still require exact validation.

The first real-embedding run retains complete predictions, diagnostics, manifests and limitations in [the 2026-10-24 record](results/2026-10-24-v101/README.md).

## Dataset scope

- 30 fully synthetic, privacy-safe sources: 20 project notes, 6 multi-language code files, and 4 Git activity records.
- 40 Chinese questions: 16 direct facts, 8 cross-document questions, 6 code-location questions, 6 temporal questions, and 4 unanswerable questions.
- Every answerable case includes a gold answer, required facts, expected entities or relations, and gold evidence identified by file, inclusive lines, and an exact quote.
- Unanswerable cases intentionally contain no gold evidence and test evidence-grounded refusal.

This is the reproducible V1 experiment set, not a claim of external validity on a real medium repository. A public repository, 30–50 personal notes, and real-provider quality remain separate experiments and must not be combined with these synthetic results.

## Layout

```text
evaluation/
├─ manifest.json            # Version, counts, and category distribution
├─ case.schema.json         # JSON Schema for one gold case
├─ prediction.schema.json   # JSON Schema for one prediction
├─ cases.jsonl              # 40 questions, answers, and evidence records
├─ reviewed_graph.json      # Corpus-only synthetic annotations and replay timeline
└─ corpus/
   ├─ docs/                 # Project notes
   ├─ code/                 # Python, TypeScript, Java, and Go code
   └─ git/                  # Commit, Issue, PR, and Review records
```

The validator derives `fingerprint_sha256` from the manifest, cases, and every corpus byte. Record the dataset version and fingerprint in every experiment report.

## Validate the gold set

Run from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_dataset validate --dataset ..\evaluation
```

The validator checks manifest counts, unique IDs, field and timestamp constraints, relation types, answerability rules, safe source paths, and exact UTF-8 line/quote matches. It performs no network, database, model, or embedding calls.

## Prepare an experiment project

Prefer all three modes on one newly prepared project with a frozen graph/index. Separate initialized copies are also supported, but compare actual knowledge and index fingerprints rather than corpus identity alone.

1. Upload and parse all 30 sources while preserving paths under `corpus/`.
2. Reuse the same human-confirmed entities, relationships, evidence, and temporal replacement records in all groups. Unreviewed extraction output is not gold knowledge.
3. Do not build embeddings for the keyword group. Use the same embedding model, dimensions, and index snapshot for the vector RAG and hybrid groups.
4. Send temporal cases with the exact `valid_at` value from `cases.jsonl`.
5. Record mode, model names, parameters, start time, dataset version, and fingerprint. Never store secrets, full raw model responses, or private source bodies in result files.

A standalone initializer replays `reviewed_graph.json` through ordinary ingestion, parsing, candidate confirmation and evolution review services. It never directly creates formal graph records. Names, summaries and relationships come only from the corpus, not evaluation questions or answers. The operator explicitly accepts the synthetic annotations; these replayed decisions are not real-user review history or extraction-model quality evidence.

Run from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_evaluation --dataset ..\evaluation --validate-only
.\.venv\Scripts\python.exe -m scripts.prepare_evaluation `
  --dataset ..\evaluation `
  --output-dir ..\output\evaluation\preparation-v101 `
  --accept-curated-fixture
```

Prerequisites: migration `20261023_0015` and a `development/test/evaluation` environment. The initializer creates a new `[EVAL]` project; `--project-id` may specify an unused UUID. Existing projects and output directories are always refused. An outer transaction encloses service savepoints and rolls back all new data on failure. Expected counts: 30 sources, 109 chunks, 60 tasks, 44 entities, 10 semantic relationships, 90 evidence records, 54 review events and one evolution change. `preparation.json` records project/mappings, dataset/annotation/actual-knowledge fingerprints and `synthetic_history=true` without credentials.

The synthetic clock is scoped to formal promotion in this standalone process and restored afterward. Never invoke the initializer inside an API/Worker process. No application backdating API is introduced. UI preparation remains available, but ordinary current-time reviews cannot automatically satisfy historical evaluation dates.

After explicitly authorizing real embedding calls, build the index and run all three retrieval-only groups:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_baselines `
  --dataset ..\evaluation `
  --preparation-report ..\output\evaluation\preparation-v101\preparation.json `
  --output-dir ..\output\evaluation\baselines-v101 `
  --allow-embedding-calls --embedding-batch-size 10
```

A first complete run makes at most five index requests and 80 query embedding requests, with zero answer calls. Batch size applies only to the command, without changing `.env`. `baselines.json` records successful/failed calls, texts and characters; billing tokens/cost stay `null` when unavailable. `comparison.csv/md` reports evidence recall, mean/P95 latency and positive graph hits. Failures retain status/partial predictions; the command never automatically retries or overwrites an existing directory.

## Run the experiment groups

The experiment runner reads one prepared isolated project. It does not import sources, write formal knowledge, or overwrite an existing output directory. Its default command performs keyword retrieval only and makes no model or embedding-provider calls:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_evaluation `
  --dataset ..\evaluation `
  --project-id <project UUID> `
  --output-dir ..\output\evaluation\keyword-run
```

Vector and hybrid modes call the embedding provider once per question and therefore require explicit authorization:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_evaluation `
  --dataset ..\evaluation `
  --project-id <project UUID> `
  --output-dir ..\output\evaluation\retrieval-run `
  --modes keyword vector hybrid `
  --allow-embedding-calls
```

Only `--with-answers` authorizes DeepSeek calls when retrieved evidence exists. A complete three-mode answer run can make up to 80 query-embedding calls and 120 answer calls; evidence-empty cases do not call the answer provider. Run the three retrieval experiments first, inspect cost and output, and enable answers separately.

Preflight requires exactly the 30 frozen files, matching names and SHA-256 hashes, all in `ready` state. Vector and hybrid runs additionally require every visible formal entity to be indexed. Evidence outside the corpus fails the run. A new output directory contains `run.json`, one `<mode>.jsonl` prediction file and `<mode>.metrics.json` report per completed mode, plus `<mode>.partial.jsonl` only after an interrupted mode. The manifest records dataset identity, modes, Top K, model names, explicit provider authorization, successfully completed provider-call counts, and status without credentials, database URLs, or raw provider responses. `latency_ms` covers retrieval alone unless answers are enabled, in which case it covers retrieval plus answering.

Each mode also saves `<mode>.diagnostics.jsonl` with hit-level keyword/vector/graph/hybrid scores and graph-signal counts; incomplete diagnostics retain `.partial.jsonl`. Actual graph and vector-index fingerprints are captured and rechecked after each mode; data changes fail the run. Synthetic curated-graph retrieval results do not establish real-repository, extraction or answer quality. The current keyword baseline splits on whitespace and can return no hit for a complete Chinese question; report this limitation transparently.

## Prediction contract

The scorer consumes JSONL with exactly one record per case. See `prediction.schema.json` for the complete contract.

```json
{"id":"direct-003","retrieved_evidence":[{"source":"corpus/docs/07_upload_limits.md","start_line":5,"end_line":5,"quote":"一次文件夹或 GitHub 快照最多选择 50 个支持文件。"}],"citations":[{"source":"corpus/docs/07_upload_limits.md","start_line":5,"end_line":5,"quote":"一次文件夹或 GitHub 快照最多选择 50 个支持文件。"}],"answer":"一次最多选择 50 个支持文件。","supported":true,"latency_ms":183.4,"answer_correct":true,"explainability_score":5}
```

`retrieved_evidence` must preserve retrieval order. `citations` contains only evidence actually cited by the final answer. Retrieval-only runs set `answer` and `supported` to `null`, leaving answer and citation metrics unscored instead of marking them wrong. Map API titles back to their unique corpus-relative paths. Human reviewers set `answer_correct` and `explainability_score`; omit them or use `null` while they remain ungraded.

An answer is manually correct only when it covers every `required_facts` item, adds no contradictory claim, uses the correct temporal snapshot, and refuses unanswerable questions without invention. Explainability uses a 1–5 scale, from no traceable citation to complete, exact evidence with clear cross-document or temporal reasoning.

## Score predictions

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_dataset score `
  --dataset ..\evaluation `
  --predictions ..\output\evaluation\hybrid.jsonl `
  --output ..\output\evaluation\hybrid.metrics.json
```

The report includes macro evidence Recall@1/3/5, citation precision/recall/F1 and evaluation coverage, supported-or-refusal accuracy, required-fact coverage, manually graded answer accuracy and coverage, cross-document and temporal accuracy, mean/P95 latency, and explainability mean/coverage. Predictions must cover all 40 cases. Retrieval-only reports keep answer metrics null with zero coverage. Deterministic required-fact coverage is an aid, not a substitute for manual answer grading.

## Optional source-location mode

`scripts.run_evaluation --modes bm25 bm25_source` supports a provider-free comparison in a new output directory. Defaults and old protocol remain unchanged. See [diagnostic](results/2026-10-25-source-mode/README.md) and [new functional cases](regressions/source-location-v1/README.md); neither provides human answer-quality grades.
