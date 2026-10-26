# ADR 0053：资料列表字段裁剪与搜索证据批量读取

状态：已接受 · 日期：2026-10-26

[English](0053-batched-read-paths.md)

## 决策

先测原生读取路径再优化。资料分页仅选择列表字段，省略列启用 raiseload；按用户/项目/该页来源限定的 row_number 分组只取每份来源最新解析任务，保留 created_at/ID 排序。详情与解析仍按需读取原文。

各搜索模式共用 graph.evidence_for_records：每批必须为同一用户、项目和所有者种类，作用域连接来源/分块/仓库，并统一批量解析 Git 来源链接。保持每个所有者的证据顺序、UUID/精确摘录/行号链接、原排序、限制、响应结构及证据数量。单项详情保留包装函数；RRF 使用有界词法与仅向量命中批次，不再逐实体读取。

## 影响

原生 100 来源/每来源 20 任务夹具记录查询数、耗时和 Python 分配峰值，见[独立测量](../../evaluation/performance/2026-10-26-read-paths/README.zh-CN.md)。规范化响应指纹全部相同。测量只覆盖本机服务，不含 HTTP 延迟、RSS、数据库内存或代表性生产容量。不据此增加索引、缓存、供应商调用或改动排序。BM25 仍保留有界扫描，大语料排序另行评估。

在 backend 运行 `python -m scripts.benchmark_reads --output ../output/reads.json`，需本机 PostgreSQL/pgvector 与 CREATE SCHEMA。脚本迁移随机私有 schema、证明所有表物理归属后写合成夹具，经正常审核/提升生成知识，并仅清理自建 schema；应用业务表与迁移标记必须不变。
