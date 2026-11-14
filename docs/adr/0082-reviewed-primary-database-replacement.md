# ADR 0082 Reviewed primary database replacement

[简体中文](0082-reviewed-primary-database-replacement.zh-CN.md)

## Decision

Extraction can classify a `USES` relation as `primary_database` when a verified quote explicitly identifies the service, its primary database and the technology name. The system can also recognize those words in evidence from older confirmed relations.

For the first version, the service identity is the normalized name and entity type within one project. The review page offers a replacement when one different primary database relation from another source overlaps the new interval, started before the new effective time and has accessible evidence. Ambiguous overlaps, missing dates and repeat values require review. Ordinary `USES` relations retain their existing behavior.

The reviewer sees both facts and their evidence and submits a fingerprint of the displayed proposal. Under the project lock, the backend revalidates the proposal and commits the new relation, the old relation's closing time and a directed `SUPERSEDES` audit record in the same transaction. The new relation points to the existing service node. Historical queries continue to use half-open intervals and each relation retains its own evidence. Replacement proposals cannot be approved as part of batch confirmation.

## Storage

Classification and the approval receipt live in candidate JSON and the directed replacement snapshots live in the existing review event. PostgreSQL remains authoritative. No schema migration is required. The existing entity evolution workflow remains available for entity-level changes.
