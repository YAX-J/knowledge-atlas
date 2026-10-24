# 跨文件调用金标集

[English](README.md)

版本 1.0.0 包含 30 份公开合成源码片段、50 道精确到行的案例，每种语言 5 题：Python、JavaScript、JSX、TypeScript、TSX、Go、C、C++、C#、Java。场景为唯一目标、限定接收者、未知/开放分派、外部调用和封闭分派。金标是人工编写的期望，不是编译器生成的真值；片段不是完整可构建仓库。包含用于边界测试的无害提示注入注释，但不会执行任何源码。

在 `backend` 运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_calls --dataset ..\evaluation\calls --validate-only
.\.venv\Scripts\python.exe -m scripts.evaluate_calls --dataset ..\evaluation\calls --mode static --output-dir ..\output\calls-static
```

模型模式 `single_step`、`tools` 另需 `--allow-model-calls` 和用户明确授权。输出目录必须全新。三种方式共用有界候选生成器，模型不能发明目标 ID。候选覆盖与判定能力分别统计：未知金标没有目标，歧义金标要求精确目标集合；评分检查案例完整且不重复，并比较状态、路径与声明行。

[真实运行报告](../results/2026-10-24-models/REPORT.zh-CN.md)同时保留提升与不足。每种语言仅 5 题，不能据此声称普遍语言能力、统计显著性、运行时分派正确性或抵御全部提示注入。
