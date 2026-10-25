# ADR 0052: Verified native PostgreSQL backups and guarded restore

[简体中文](0052-verified-native-backups.zh-CN.md)

Status: Accepted

Date: 2026-10-25

## Decision

Use native `pg_dump` custom archives with an exported read-only repeatable-read snapshot. Record archive SHA-256 and a same-snapshot fingerprint of every application table's row count/canonical JSONB content, columns, exact types, constraints, indexes and extensions. Credentials enter child-process environment only. Backups use new directories and never overwrite prior artifacts.

Restore validates the checksum before writing and only creates a fresh `ka_restore_*` database; existing/configured databases are refused. It uses `pg_restore --exit-on-error --single-transaction` and validates the restored fingerprint. Roles, credentials and cluster-wide configuration are outside this database backup.

For public-only application backups and roles lacking CREATEDB, provide `restore-schema` rehearsal. The backup stores reflected application DDL with explicit foreign-key remapping. Rehearsal creates a new schema, validates physical table ownership and absence of foreign keys to application tables, then streams COPY blocks only into those tables in dependency order. It never executes data-file SQL against public. Every row, exact type and structural fingerprint must match. Normalize only PostgreSQL's redundant varchar/text-array CHECK rendering; retain boolean grouping. This fallback does not verify database creation, role grants or an entire cluster restore.

Only trusted locally generated archives/manifests are inputs. `--cleanup` removes only the validated target created by that invocation, never an existing target. Restore does not change application configuration or activate restored data.

## Consequences

Recovery is reproducible without a new service/dependency. Local isolated-schema recovery of 18 tables passes with unchanged application data. Full new-database restore needs CREATEDB and extension-creation privileges and remains unverified under the current application role. See [operations guide](../BACKUP_RESTORE.md). Native options follow [pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html) and [pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html).
