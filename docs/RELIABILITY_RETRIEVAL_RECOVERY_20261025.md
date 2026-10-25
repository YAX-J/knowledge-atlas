# Optimization items 1–3 acceptance — 2026-10-25

[简体中文](RELIABILITY_RETRIEVAL_RECOVERY_20261025.zh-CN.md)

Implemented in the requested order:

1. Durable index rebuild ownership/status and explicit interruption recovery, with separate unavailable-read/unknown-write outcomes and bounded model-request waiting. [ADR 0050](adr/0050-durable-index-rebuilds.md).
2. Optional source-aware lexical search/questions, nine new isolated functional cases and a separate replay on the old 40-case development set. [ADR 0051](adr/0051-source-aware-lexical-retrieval.md).
3. Native consistent-snapshot backup, archive/structure/content verification and guarded fresh-target recovery. [ADR 0052](adr/0052-verified-native-backups.md), [operations](BACKUP_RESTORE.md).

## Executed verification

The user selected agent execution. No real model/embedding or GitHub calls were made.

| Check | Actual result |
| --- | --- |
| Backend focused | `python -m pytest tests/test_embedding_jobs.py tests/test_source_retrieval.py tests/test_database_backup.py tests/test_migrations.py tests/test_run_evaluation.py --tb=short --show-capture=no`: 40 passed |
| Full backend | `python -m pytest --cov=app --cov-fail-under=90 --cov-report=term --cov-report=xml:../output/backend-coverage.xml --tb=short --show-capture=no`: 662 passed, 6 skipped; 94.58% statement coverage |
| Native database | `python -m scripts.verify_native`: PostgreSQL 17.10 / pgvector 0.8.7 upgrade/downgrade/upgrade and independent-session duplicate rebuild/status checks passed, including new retrieval cases; temporary schema removed and application migration marker unchanged during the isolated suite |
| Frontend focused | `npm test -- tests/knowledgeSearchState.test.ts tests/workspaces.test.ts tests/client.test.ts tests/appRequests.test.ts`: 47 passed before the final timeout-budget regression |
| Final frontend | `npm run test:coverage`: 69 passed across 8 files; configured statements 65.56%, branches 63.87%; `npm run build` passed |
| Backup guards | `python -m pytest tests/test_database_backup.py`: 5 passed after final CLI changes |
| Real backup/recovery | Native snapshot backup and isolated-schema recovery passed first for 17 tables, then for all 18 tables after migration; row/content/type/constraint/index/extension fingerprints matched and all targets were removed |
| Application migration | After the verified pre-migration backup and isolated native acceptance, `alembic upgrade head` applied `20261025_0016`; existing business table fingerprints were unchanged |
| Desktop browser | Chrome 1440 × 1100: interrupted job requires explicit retry; refresh during a delayed local embedding restores running state and disables duplicate update; state inspection shows completion; lost successful response displays unknown outcome/status inspection and sends one POST; bm25_source matches four reviewed knowledge items by filename with provenance explanation |
| Accessibility | Search-region axe: 0 violations / 0 incomplete checks; no horizontal overflow or browser errors observed |
| Repository | Before commit: `git diff --check`, local Markdown links, staged diff and generated/credential-file hygiene checked |

The existing Starlette/httpx deprecation warning remains. Frontend coverage is a configured subset, not whole-application coverage. Named browser, recorded QA services and private fixture schema were cleaned up; fixture UUID was absent from public. Temporary artifacts and private database backups remain ignored under `output/reliability-123-20261025/`; final usable backup is `final-backup-0016/`.

## Retrieval findings

Both modes used the same frozen corpus/knowledge/index fingerprints, with 0 provider requests. Old BM25 Recall@1/3/5: **60.74% / 68.24% / 74.49%**. Source-aware mode: **60.05% / 69.17% / 74.49%**. It does not improve aggregate Recall@5, so it remains optional for location queries and no default is changed. Full artifacts: [new diagnostic](../evaluation/results/2026-10-25-source-mode/README.md).

The nine new functional cases were authored during development and use isolated synthetic fixtures. They are not held-out or representative quality measurements. Misleading-overlap refusal uses a stub provider response and verifies the application contract, not real model judgment. Human answer quality and general multi-hop/code reasoning remain ungraded.

## Recovery boundary

The current application role has CREATE SCHEMA but lacks CREATEDB. PostgreSQL rejected the full fresh-database restore attempt; no permissions were changed. Instead, actual recovery was verified in a new schema, including explicit foreign-key remapping, no references to public application tables, live foreign-key checks during data copying and complete application-table fingerprints. This does not count as a completed new-database/cluster disaster-recovery test.

Backup roles/server configuration/credentials are outside scope. Only trusted local archives/manifests are supported. Rebuilds remain synchronous; the server records the latest operation, not a background job queue or full history. Questions/call analysis remain non-persistent. Explicit interrupted retries can incur additional provider billing; exactly-once billing and server cancellation are not promised.
