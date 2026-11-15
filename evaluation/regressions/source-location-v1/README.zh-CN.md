# 来源位置功能回归


cases.json 的 9 个合成案例在本次实现期间独立于既有 40 题语料编写，覆盖 Java/Python/TypeScript 文件名/路径、中文标题、直接事实、无匹配词及误导性词面重叠。`backend/tests/test_source_retrieval.py` 中每例均经隔离的普通上传→解析→模拟抽取→显式审核→正式证据链路。

这是小型功能回归，不是共享大语料排序基准或保留测试集的人工质量测评，不调用真实供应商。误导重叠案例由测试提供证据不足响应以验证拒答契约，不证明真实模型能正确拒答；原提示词/引用约束另有独立测试。

在 backend 运行 `python -m pytest tests/test_source_retrieval.py`。另有[40 题诊断](../../results/2026-10-25-source-mode/README.zh-CN.md)在既有开发语料比较新模式，不覆盖历史报告。
