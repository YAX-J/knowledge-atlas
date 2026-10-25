# ADR 0047: Filtered knowledge discovery and complete passage attribution

[简体中文](0047-filtered-discovery-evidence-attribution.zh-CN.md)

Status: Accepted

Date: 2026-10-25

## Decision

Extend candidate listing with optional `kind=entity|relation` and `q` (at most 200 characters). Combine them with existing source/status/type/confidence filters before counting and pagination. Match normalized query whitespace as a literal case-insensitive substring of name or summary, escaping SQL wildcards. Preserve the unfiltered default and source-wide extraction review totals. Frontend filter changes return to page one, clear selections/previews and invalidate prior responses; after review, recover from a page that no longer exists.

Governance accepts an optional finding `kind` filter. Count categories across the bounded scan and filter before applying the result limit; return `counts_by_kind` and `kind_filter`. Counts describe only the inspected current-knowledge scope, not complete semantic quality. Defaults, stable finding IDs, the 1000-entity scan budget and read-only behavior remain intact.

Add an explicit two-entity comparison view using existing authorized entity-detail reads. Validate returned IDs and project ownership before displaying either result, present each source independently and retain exact original-evidence navigation. Closing, changing project/time/category or resolving a change invalidates comparison results. The view performs no merge or knowledge mutation.

Online question evidence still deduplicates exact source/chunk/line/quote locations and uses the original canonical evidence ID. Add `related_entities` from all retrieved entities sharing a selected passage; send their names as `entity_names` with the passage to the answer provider. Preserve primary `entity_id`/`entity_name` and the response's primary `entity_ids` semantics. All citation IDs must still belong to the canonical evidence actually sent. No persisted evidence is merged and distinct sources/versions stay separate.

## Consequences

Users can work through relevant review queues and compare potentially duplicate evidence without changing authoritative knowledge. A shared quote no longer loses its other entity attributions. Existing retrieval rankings, answer schema validation, defaults and historical experiments remain stable. No database migration, new provider dependency or model-quality claim is introduced.
