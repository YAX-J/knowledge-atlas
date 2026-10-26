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
- [ADR 0008：带证据的项目关键词检索](0008-project-keyword-search.zh-CN.md)
- [ADR 0009：显式构建正式知识语义索引](0009-explicit-semantic-index.zh-CN.md)
- [ADR 0010：融合一跳图信号的可解释混合检索](0010-explainable-hybrid-graph-retrieval.zh-CN.md)
- [ADR 0011：使用同步问答与受校验引用实现证据回答](0011-synchronous-evidence-grounded-questions.zh-CN.md)
- [ADR 0012：使用保留行号的有界 Java 源码导入](0012-bounded-java-source-ingestion.zh-CN.md)
- [ADR 0013：在正式图谱之外派生有界 Java 源码结构](0013-derived-java-source-structure.zh-CN.md)
- [ADR 0014：按需解析有界的跨文件 Java 类型关系](0014-bounded-cross-file-java-types.zh-CN.md)
- [ADR 0015：在项目内标识本地文件夹来源仓库](0015-local-folder-repository-identity.zh-CN.md)
- [ADR 0016：在仓库导入前规范化 GitHub remote 身份](0016-normalized-github-remote-identity.zh-CN.md)
- [ADR 0017：按需解析有界的跨文件 Java 方法调用](0017-bounded-cross-file-java-method-calls.zh-CN.md)
- [ADR 0018：显式导入有界的 GitHub 仓库快照](0018-bounded-github-snapshot-import.zh-CN.md)
- [ADR 0019：持久化增量 GitHub Commit 快照](0019-incremental-github-commit-snapshots.zh-CN.md)
- [ADR 0020：从快照派生不可变 GitHub 证据链接](0020-derived-immutable-github-evidence-links.zh-CN.md)
- [ADR 0021：把有界 GitHub 工作项导入为不可变来源版本](0021-versioned-github-work-items.zh-CN.md)
- [ADR 0022：解析通过显式声明接收者发起的有界 Java 调用](0022-bounded-java-declared-receiver-calls.zh-CN.md)
- [ADR 0023：独立版本化有界 GitHub Pull Request Review 活动](0023-versioned-github-pull-reviews.zh-CN.md)
- [ADR 0024：通过 GraphQL 快照化有界 GitHub Review thread 状态](0024-bounded-github-review-thread-state.zh-CN.md)
- [ADR 0025：从构造器初始化推断有界 Java var 接收者](0025-constructor-initialized-java-var-receivers.zh-CN.md)
- [ADR 0026：在有界词法块内解析 Java 局部接收者](0026-scoped-java-local-receivers.zh-CN.md)
- [ADR 0027：通过有界增强 for 元素解析 Java 接收者](0027-enhanced-for-java-receivers.zh-CN.md)
- [ADR 0028：在有界异常作用域内解析 Java 调用](0028-java-exception-scope-receivers.zh-CN.md)
- [ADR 0029：打包有界仓库内 Java 分析 V1](0029-java-analysis-v1.zh-CN.md)
- [ADR 0030：解析有界仓库内 Java 静态导入调用](0030-java-static-import-calls.zh-CN.md)
- [ADR 0031：以类型安全的来源复用恢复不完整 GitHub 快照](0031-recoverable-typed-github-snapshots.zh-CN.md)
- [ADR 0032：检索有界 Java 源码符号并打开原文分块](0032-bounded-code-symbol-search.zh-CN.md)
- [ADR 0033：将已保存的提交说明导入为证据来源](0033-saved-commit-evidence-sources.zh-CN.md)
- [ADR 0034：查询已保存的快照逐文件来源](0034-snapshot-file-provenance.zh-CN.md)
- [ADR 0035：从证据跳转到精确原文分块](0035-exact-evidence-source-navigation.zh-CN.md)
- [ADR 0036：从静态工厂调用推断有界 Java `var` 接收者](0036-bounded-java-static-factory-var-receivers.zh-CN.md)
- [ADR 0037：解析未限定名 Java 工厂接收者](0037-unqualified-java-factory-receivers.zh-CN.md)
- [ADR 0038：在循环与资源头部推断 Java 工厂接收者](0038-java-header-factory-receivers.zh-CN.md)
- [ADR 0039：显式审核跨来源知识演化](0039-reviewed-knowledge-evolution.zh-CN.md)
- [ADR 0040：扩展代码多语言解析而不改变知识权威边界](0040-multilanguage-source-parsing.zh-CN.md)
- [ADR 0041：通过 Agent 执行有界多语言跨文件调用分析](0041-bounded-multilanguage-agent-call-analysis.zh-CN.md)
- [ADR 0042：通过审核服务重放可复现的合成实验项目](0042-reproducible-curated-evaluation-projects.zh-CN.md)
- [ADR 0043：有界只读仓库工具 Agent](0043-bounded-read-only-tool-agent.zh-CN.md)
- [ADR 0044：新增有界离线词法检索基线](0044-bounded-offline-bm25-search.zh-CN.md)

- [0045: 可选排名融合与在线证据分配](0045-opt-in-rank-fusion.zh-CN.md)

- [0046: 显式整批审核与只读索引状态](0046-atomic-batch-review-index-status.zh-CN.md)

- [0047: 筛选发现与原文实体归属](0047-filtered-discovery-evidence-attribution.zh-CN.md)

- [0048: 关系审核依赖可见性](0048-review-endpoint-visibility.zh-CN.md)

- [0049: 资料组合筛选与分页恢复](0049-source-discovery-filters.zh-CN.md)

- [0050: 持久化索引更新与未知结果](0050-durable-index-rebuilds.zh-CN.md)

- [0051: 可选来源位置词法检索](0051-source-aware-lexical-retrieval.zh-CN.md)

- [0052: 可验证原生备份与受控恢复](0052-verified-native-backups.zh-CN.md)

- [ADR 0053: 资料列表与搜索证据批量读取](0053-batched-read-paths.zh-CN.md)

- [ADR 0054: 保留历史的审计停用](0054-audited-knowledge-retirement.zh-CN.md)

- [ADR 0055: 按上下文分离工作台编排](0055-scoped-workspace-orchestration.zh-CN.md)
