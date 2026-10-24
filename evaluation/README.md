# Knowledge Atlas Evaluation Set

[简体中文](README.zh-CN.md)

This directory contains the frozen evaluation set shared by the Stage 6 experiments. It versions the corpus, questions, gold answers, and line-exact gold evidence together so keyword, vector RAG, and knowledge-graph hybrid retrieval use the same inputs and scoring rules. The set makes no external model calls and does not claim real DeepSeek or embedding-provider quality acceptance.

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

Use a separate empty project per experiment group so existing knowledge cannot affect the result.

1. Upload and parse all 30 sources while preserving paths under `corpus/`.
2. Reuse the same human-confirmed entities, relationships, evidence, and temporal replacement records in all groups. Unreviewed extraction output is not gold knowledge.
3. Do not build embeddings for the keyword group. Use the same embedding model, dimensions, and index snapshot for the vector RAG and hybrid groups.
4. Send temporal cases with the exact `valid_at` value from `cases.jsonl`.
5. Record mode, model names, parameters, start time, dataset version, and fingerprint. Never store secrets, full raw model responses, or private source bodies in result files.

There is intentionally no fixture loader that writes directly to the formal graph because formal knowledge must pass review. Use the existing UI or API to import, extract, and confirm the shared experiment project before collecting predictions.

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
