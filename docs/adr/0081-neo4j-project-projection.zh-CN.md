# ADR 0081 可选的 Neo4j 项目图谱快照


2026-11-13 接受。已使用本机 Neo4j Desktop 和 PostgreSQL 验证。

PostgreSQL 继续作为正式知识、证据、审核、身份与时序历史的权威存储。默认图谱和检索接口仍使用 PostgreSQL 和 pgvector。本决策更新 [ADR 0005](0005-postgresql-only-storage.zh-CN.md) 对 Neo4j 的安排，引入可选、可重建的项目快照。

按项目显式同步，读取 `valid_at` 时刻可见的正式图谱，默认取同步时间。同步复用 PostgreSQL 的可见性、有效区间、规范化端点和证据计数。项目行锁让快照操作与正式图谱更新串行。Neo4j 在一个数据事务中替换该范围内的旧快照并记录有效时间。项目超过 5,000 个节点或 20,000 条关系时，接口在写入快照数据前拒绝同步。重复同步可以重建快照。

Neo4j 的 `KnowledgeEntity` 节点沿用已有的业务 UUID 唯一约束，应用管理的快照节点还带 `KAProjectionEntity` 标签。有向 `KA_RELATIONSHIP` 边保存正式关系 UUID 与业务 `type`。快照保留用户和项目范围。可选的读取接口用 Cypher 查询有界邻域，并返回当前快照的有效时间。每次刷新都替换旧快照，也可以显式指定更早的时间。

Neo4j 连接信息独立配置。单独的连通检查和快照接口会返回连接失败。核心 API 就绪仍依赖 PostgreSQL 与其 schema。知识发生变化后可显式刷新。使用 Neo4j Desktop 可在本机验收，无需 PostgreSQL 迁移。配置和命令见[环境配置](../DEVELOPMENT_SETUP.zh-CN.md)。

本机使用 Neo4j 2026.10.2 验证。连通接口返回 200，现有 `test` 项目两次同步均返回 7 个节点和 2 条关系，无中心查询和一跳、两跳查询均与 PostgreSQL 在同一快照时间的结果一致。后端全量回归 1,113 项通过、13 项跳过，覆盖率 95.49%。
