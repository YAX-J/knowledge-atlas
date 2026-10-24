# Cross-file call gold set

[简体中文](README.zh-CN.md)

Version 1.0.0 contains 30 public synthetic source snippets and 50 line-exact cases: five per language (Python, JavaScript, JSX, TypeScript, TSX, Go, C, C++, C#, Java). Scenarios cover unique targets, receiver qualification, unknown/open dispatch, external calls and closed dispatch. Gold decisions are authored expectations, not compiler-generated ground truth. Snippets are not complete buildable repositories. The corpus includes inert adversarial comments; no source is executed.

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_calls --dataset ..\evaluation\calls --validate-only
.\.venv\Scripts\python.exe -m scripts.evaluate_calls --dataset ..\evaluation\calls --mode static --output-dir ..\output\calls-static
```

Model modes `single_step` and `tools` require `--allow-model-calls` and separate user authorization. Output directories must be new. All three modes share the same bounded candidate generator; the model cannot invent target IDs. Candidate coverage is measured separately from decisions. An unresolved gold case has no target; ambiguous cases require the exact target set. Scoring requires every case exactly once and compares status plus path/declaration line.

The [real run](../results/2026-10-24-models/REPORT.md) demonstrates limitations as well as improvements. Five cases per language cannot establish language-wide quality, statistical significance, runtime dispatch correctness or resistance to all prompt injection.
