# Source-location functional regressions

[简体中文](README.zh-CN.md)

Nine synthetic cases in `cases.json` were authored separately from the existing 40-question corpus during this implementation. They exercise Java/Python/TypeScript filename/path lookup, Chinese headings, direct facts, absent terms and misleading lexical overlap. Each uses an isolated normal upload → parse → stub extraction → explicit review → formal-evidence pipeline through `backend/tests/test_source_retrieval.py`.

These are small functional regressions, not a representative shared-corpus ranking benchmark or held-out human-quality evaluation. No real provider is called. For misleading overlap, the test supplies an unsupported provider response to validate the refusal contract; it does not prove a real model refuses correctly. Existing prompt/citation checks remain independently tested.

Run from backend: `python -m pytest tests/test_source_retrieval.py`. The separate [40-question diagnostic](../../results/2026-10-25-source-mode/README.md) measures the new mode on the existing development corpus without replacing historical reports.
