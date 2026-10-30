# ADR 0071: Bounded symbol metadata and lightweight workflow history

[简体中文](0071-bounded-read-caches-and-summaries.zh-CN.md)

- Status: Accepted
- Date: 2026-10-30

## Decision

After current user/project/repository/readiness and scan-budget checks, symbol search caches only immutable symbol tuples and truncation/syntax flags. Keys include user, project, source UUID, computed content SHA256, language, explicit parser revision and parser limits. Source versions cannot share UUID-derived symbol identities. Process-local locked LRU limits entries to128 and conservatively accounted metadata to8 MiB; it stores no source body, tree, parser instance, task mapping, source URL or access grant. Source/chunk/task/Git links remain live reads. Parser changes must bump SYMBOL_PARSER_VERSION; dependency upgrades restart processes. Concurrent cold requests may compute the same result twice, but do not share parser instances. This is not a persisted or distributed cache and accounted bytes are not process RSS.

Workflow lists add opt-in `summary=true`. The default remains the complete historical response. Summaries include only id/project_id/source_id/kind/status/error_code/created_at/updated_at; SQL excludes result/events/request/usage and performs3 SELECTs. The Vue list requests summaries and fetches full detail only on selection/restoration/refresh of a selected run. Full list batching and source/task/candidate review checks remain; expiry is still read-only. No schema migration is needed.

Extract AgentWorkflowForm from AgentWorkspace without changing draft reset, explicit source versions, historical exclusion or paid submission rules. Extract shared frozen syntax records into analysis/structures.py, retaining old Java/Tree-sitter imports as re-exports. IDs, line evidence and parser semantics remain the same; syntax records never write formal knowledge.

## Measurement and limits

New [versioned measurements](../../evaluation/performance/2026-10-30-cache-lexical-v2/README.md) preserve historical experiments. Synthetic50-source parser calls take326.806 ms cold and0.538–0.618 ms for repeated warm keys; output fingerprints agree and all150 repeated accesses hit. This excludes database/HTTP work. A synthetic50-run response with256 events per run shrinks from1777746 to13196 JSON bytes; it is not a claim about every real page or compression.

Native lexical v2 measures1000/10000 entities promoted through normal explicit synthetic review in physically owned temporary schemas. Both lexical modes scan the full corpus; with tracemalloc, service medians are365–497 ms at1k and3358–3969 ms at10k, with up to7.24 MB Python allocations. One warm-up is excluded, followed by3 samples per query/mode; report medians, not statistically reliable p95 or production SLA. Results do not establish model quality, RSS, database memory, cold starts or HTTP latency. No new index or ranking adjustment is justified by this small synthetic sample alone. Every disposable schema is removed; application marker stays0019.

Verification: full backend811 passed/8 skipped with KA_NATIVE_COMPILERS=1, statement coverage95.63%; native233 passed including migration upgrade/downgrade/upgrade, physical schema ownership and cleanup with unchanged application marker. Frontend133 passed/18 files, scoped statement coverage69.90%/lines74.50%, form lines97.56%; production build passed. Final evaluation-policy metadata regressions27 passed using substitutes. Desktop Chrome1440×900 verified real API summary fields/GET detail, empty/loading/read-error/retry, persisted refresh without paid replay, exact source/symbol navigation, keyboard-visible focus, scroll and no horizontal overflow. Named browser and recorded services/schema were cleaned; snapshots remain ignored under output/ordered-optimizations-20261030. No real Jev/DeepSeek/embedding calls were made.
