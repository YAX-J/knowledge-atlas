# 按序读取优化测量，2026-10-30

[English](README.md)

本目录为新增的合成本地测量，不是留出集回答质量；旧结果不改。原生夹具均使用显式迁移、物理归属已校验的临时 schema，结束后删除，应用版本保持20261029_0019。真实供应商调用为0。

- [符号缓存](symbol-cache.json)：50份固定 Java/Python 代码，每份30个声明，单进程一次冷解析后3次热读。输出哈希一致，150次热访问全命中。冷326.806 ms、热0.538–0.618 ms；跟踪的峰值 Python 分配584957与1717字节，保留的缓存计量元数据871050字节。计量字节是保守预算，不是实际进程内存；不含数据库、正文加载、HTTP或冷启动。
- [历史 JSON](history-summary.json)：每条256事件、3800字符回答的合成记录。10条由355586降到2676字节，50条由1777746降到13196字节，ID/顺序一致。仅度量未压缩序列化字节，不代表网络速度、压缩或所有真实页面。
- [词法v2](lexical/run.json)：1000/10000条合成候选经正常审核确认，每实体一个来源/分块/精确证据。不改生产预算与排序。各查询/模式排除一次预热，再用新会话采3次，包含 tracemalloc 和响应序列化。重复输出哈希一致，扫描数等于语料总数。3次样本的中位数不代表p95/SLA，Python分配不含 PostgreSQL内存或RSS。

| Entities | Mode | Query | Median ms | Peak Python bytes | SELECTs |
| --- | --- | --- | --- | --- | --- |
| 1000 | bm25 | PostgreSQL | 496.696 | 1399919 | 26 |
| 1000 | bm25 | record 999 | 419.167 | 1324742 | 26 |
| 1000 | bm25_source | PostgreSQL | 480.218 | 1330277 | 26 |
| 1000 | bm25_source | record 999 | 365.297 | 1335005 | 26 |
| 10000 | bm25 | PostgreSQL | 3357.603 | 7231583 | 161 |
| 10000 | bm25 | record 9999 | 3367.718 | 7139972 | 161 |
| 10000 | bm25_source | PostgreSQL | 3968.589 | 7177825 | 161 |
| 10000 | bm25_source | record 9999 | 3869.653 | 7145658 | 161 |

在 backend 用新输出路径复现，不覆盖现有结果：

```powershell
.\.venv\Scripts\python.exe -m scripts.benchmark_symbol_cache --output ../output/new-measurement/symbol-cache.json
.\.venv\Scripts\python.exe -m scripts.benchmark_agent_history --output ../output/new-measurement/history-summary.json
.\.venv\Scripts\python.exe -m scripts.benchmark_lexical_v2 --output ../output/new-measurement/lexical --repeats 3
```

此夹具证明重复解析复用及响应减重。万级全量词法扫描仍比千级更贵，小规模合成测量不足以单独支持新增索引/缓存/调整排序。真实分布、进程内存和端到端延迟需另测，见 [ADR0071](../../../docs/adr/0071-bounded-read-caches-and-summaries.zh-CN.md)。
