# ADR 0074: Isolate per-case output errors in evaluation

[简体中文](0074-evaluation-output-error-isolation.zh-CN.md)

- Accepted:2026-10-31, under the user's explicit request to fix and retry.
- Scope: offline execution protocol v4, without changing online QA, prompts, Schema, ranking, references or judge thresholds.

## Decision

The first holdout run stopped on answer5 with `QUESTION_OUTPUT_INVALID`. Its raw failure was not retained; an explicitly authorized diagnostic retry passed the original strict checks. No deterministic field-level model defect has been established or claimed fixed. The engineering defect is escalating an observable invalid-output sample into an incomplete experiment.

Explicit `--isolate-output-errors` isolates only `QUESTION_OUTPUT_INVALID` after retrieval: preserve retrieval/input evidence, sanitized exception/static constraint codes and a null answer, count the case as an output failure and continue other independent cases. Never repeat that case, repair/fabricate its answer or loosen Schema/citation checks. Transport, authentication, rate-limit, budget, incomplete-index, evidence-membership and unknown errors still stop the run. Default v3 fail-stop behavior remains compatible.

Report total cases, valid answers, invalid outputs and coverage per method. Failures cannot silently leave denominators. The frozen numeric scorer still treats null answers as ungraded, not human-correct/incorrect. Finishing all cases with failures gives `completed_with_case_errors`, never "all answers passed."

One validated BM25 diagnostic answer may be explicitly reused within the user grant. Pin dataset/fixture/application/model/protocol, compare the complete ordered retrieval and actual input pool again, and remap temporary UUIDs only for unique exact source/line/text matches. Mismatch fails before paid indexing. Preserve provenance and original generation latency; one measurement belongs to the diagnostic phase, not the same continuous benchmark. This is neither inferred attribution nor online caching/automatic resume. This retry reserves at most1 diagnostic+95 main answer requests=96, and73 embeddings.

Judge preparation still rejects missing answers by default. Explicit `--exclude-output-errors` writes only legitimate invalid-output cases to a separate exclusions file while requiring complete prediction exports. Record total/gradable/failed counts and hash exclusions. Never fabricate substitute answers/human grades or present subset quality as full coverage. Judge calls remain separately authorized; preflight stays zero-call.

## Consequences and verification

This execution protocol changed after observing the first failure and the retry reuses one diagnostic answer. Disclose both; do not call it entirely unseen or the original preregistered single run. No answer strategy is tuned against test cases; models may still return invalid output. Development/local-substitute checks cover case isolation, infrastructure fail-stop, exact reuse/mismatch rejection, exclusions and coverage. Live evidence is recorded separately.
