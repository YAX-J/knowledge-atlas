# 架构决策记录

[English](README.md)

架构决策记录（Architecture Decision Record，ADR）用于保存长期有效的选择。这些选择会影响多个组件、数据语义、安全、部署或后续实施。

## 何时增加 ADR

决策改变以下任一内容时，应增加 ADR：

- 事实来源或跨数据库同步规则。
- 知识实体、关系、证据或时序语义。
- 公共 API 约定。
- 主要框架、存储、队列、模型服务或部署选择。
- 安全边界或私有开发数据的处理方式。

小型重构和局部组件选择通常不需要 ADR，除非会约束后续工作。

## 文件命名

使用四位序号和简短的小写名称：

```text
0001-postgresql-source-of-truth.md
0002-native-svg-for-prototype-graph.md
```

序号不得重复使用。被替代的记录仍保留在仓库中。中文版使用相同序号和 `.zh-CN.md` 后缀，不占用新序号。

## 状态取值

- `Proposed`：已提出，讨论中。
- `Accepted`：已接受，当前采用。
- `Superseded`：已被更新的 ADR 替代。
- `Rejected`：已评估但未采纳。

## 模板

```markdown
# ADR NNNN 决策标题

- Status: Proposed
- Date: YYYY-MM-DD

## 背景

哪类问题或约束需要作出决策？

## 决策

决定采用什么方案？

## 影响

哪些事情会更容易、更困难，哪些成为必要条件，哪些明确不支持？

## 评估过的替代方案

评估过哪些可信的替代方案，为什么没有选择？
```

ADR 改变相关假设时，同步更新架构、API、知识模型和环境配置文档。

## 已有决策

- [ADR 0001：PostgreSQL 作为事实来源](0001-postgresql-source-of-truth.zh-CN.md)（已被 ADR 0005 替代）
- [ADR 0002：原型图谱使用原生 SVG](0002-native-svg-for-prototype-graph.zh-CN.md)
- [ADR 0003：持久化 Markdown 分块并显式执行解析](0003-markdown-parsing-execution.zh-CN.md)
- [ADR 0004：带执行租约的数据库解析 Worker](0004-database-backed-parsing-worker.zh-CN.md)
- [ADR 0005：仅使用 PostgreSQL，暂缓引入 Neo4j](0005-postgresql-only-storage.zh-CN.md)
- [ADR 0006：显式 DeepSeek 候选提取与证据审核](0006-deepseek-candidate-review.zh-CN.md)
- [ADR 0007：将已确认候选写入 PostgreSQL 正式图谱](0007-confirmed-postgresql-graph.zh-CN.md)
