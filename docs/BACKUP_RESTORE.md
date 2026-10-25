# Native backup and restore

[简体中文](BACKUP_RESTORE.zh-CN.md)

Run from `backend/` with the existing virtual environment and native PostgreSQL tools. The CLI reads `DATABASE_URL` from backend `.env` without printing it. Use only archives and manifests you generated and trust; they contain application data and restore DDL. Keep the backup directory private and outside Git. The default examples below use ignored `output/`.

```powershell
# New directory required; never overwrite an earlier backup.
.\.venv\Scripts\python.exe -m scripts.database_backup backup --directory ../output/backups/manual-20261025

# Full restore: fresh database only; needs CREATEDB and extension creation privileges.
.\.venv\Scripts\python.exe -m scripts.database_backup restore --directory ../output/backups/manual-20261025 --target ka_restore_manual_20261025

# Current application role lacks CREATEDB: verify a public-only application backup in a fresh schema instead.
.\.venv\Scripts\python.exe -m scripts.database_backup restore-schema --directory ../output/backups/manual-20261025 --target ka_restore_rehearsal_20261025 --cleanup
```

Append `--bin-dir 'C:/Program Files/PostgreSQL/17/bin'` if tools are not discoverable. The script uses PATH or native Windows PostgreSQL installations by default. It supports local PostgreSQL URLs without query overrides; it does not grant permissions or change roles.

The archive and `manifest.json` share one exported consistent snapshot. Validation covers archive checksum, every table's row count/content digest, columns, exact column types (including vector dimensions), foreign/check/key constraints, indexes, extensions and validated-constraint state. It does not back up roles, `.env`, credentials or server configuration. UUID-based application tables are the supported schema-rehearsal scope; use full database restore for additional database objects. Rehearsal refuses backups containing non-public tables rather than silently omitting them.

Existing targets and the configured application database are rejected. `--cleanup` only removes the new target created during that invocation, including on failure; without it, a newly created partial target may remain for inspection. No restore switches the application's database URL. A full production switchover is a separate operator action.

The schema fallback restores saved DDL and data, verifies all tables and foreign keys belong to the new schema before copying, streams data in dependency order and compares fingerprints. Its success proves application-table recovery in the existing server; it does not prove new-database/cluster disaster recovery.

This turn's final backup is under `output/reliability-123-20261025/final-backup-0016/`: 18 tables recovered and verified in an isolated schema, which was then removed. `20261025_0016` was applied only after the pre-migration backup and native migration acceptance; existing business data fingerprints were preserved. The current role's full new-database restore attempt was denied by PostgreSQL because CREATEDB is absent. No permission was changed. See [acceptance](RELIABILITY_RETRIEVAL_RECOVERY_20261025.md).
