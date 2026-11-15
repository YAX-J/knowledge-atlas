# ADR 0059 显式原生静态声明分析


- Status: Accepted
- Date: 2026-10-26

## Decision

扩展 ADR 0041/0043，strategy=semantic 使用可信 helper：javac parse/analyze（-proc:none、不输出、JDK17 release）、无 config/plugin/emit 的虚拟 TypeScript checker、Go 同包 parser/types。不运行用户程序、构建脚本或导入模块。将编译器声明映射到不可变路径/行证据及稳定派生 UUID，可覆盖大纲候选之外的声明。显示语法/类型上下文诊断与未解析调用；进程限 30 秒/输出预算，重复路径版本拒绝。

## Consequences and alternatives

编译器定位只代表静态声明，不代表运行时分派或完整项目语义；不推测/安装依赖及构建 classpath。C/C++/C# 保留语法/Agent 支持；SDK 缺失明确报错。原生模式不调用供应商。
