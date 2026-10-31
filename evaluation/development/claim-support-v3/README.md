# Claim support v3 development checks

[简体中文](README.zh-CN.md)

These four hand-written fictional Nimbus cases are independent development fixtures, not a frozen quality benchmark. [cases.json](cases.json) defines two source excerpts and four scenarios: all supported, mixed support, all insufficient and shared citation. No corpus, questions, failed output or judge feedback was copied from public-v2/holdout-v3. Expected flags are schema-level expectations, not model grades.

The new provider protocol is `evidence-claims-v3`: only confidence, claims and missing_information. The backend computes aggregate supported. Both correct and incorrect provider-supplied aggregates are rejected; unknown/cross-project citations, unsupported statuses, missing citations/reasons, duplicate citations, extra fields and budgets remain strict. v2 and flat history remain readable with their saved values and no new calls. See [ADR0075](../../../docs/adr/0075-server-derived-answer-support.md).

Run from backend with the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_claim_support_v3.py tests/test_answer_claims.py tests/test_questions.py tests/test_conversations.py tests/test_multi_agent.py tests/test_run_evaluation.py tests/test_evaluation_diagnostics.py --basetemp=../output/pytest-claim-v3-focused
```

The development suite uses local HTTP substitutes for single_step and tools, checking one attempted request even on rejected v2 wire output. It makes no live model/embedding/judge requests. Four valid cases plus invalid mutations test software behavior only; v3 model quality and actual malformed-output frequency remain unmeasured. Historical v2 experiments, failed outputs, denominators, exclusions, grants and scores stay unchanged. No dataset or protocol is being regraded.

Verification on 2026-10-31: the focused backend command passed 118 tests; frontend claim compatibility passed 5 tests and the production build passed. The complete backend suite passed 994 tests with 11 skipped. Frozen artifacts remain unchanged; no live providers were called. Human grading coverage remains 0%.
