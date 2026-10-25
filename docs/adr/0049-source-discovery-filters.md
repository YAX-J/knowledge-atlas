# ADR 0049: Filtered source discovery and recoverable pagination

[简体中文](0049-source-discovery-filters.zh-CN.md)

Status: Accepted

Date: 2026-10-25

## Decision

Extend source listing with optional `q` (maximum 200 characters), registered `source_type`, and `source_status=uploaded|processing|ready|failed`. Normalize query whitespace and match a literal case-insensitive substring of original filename or repository-relative path, escaping SQL wildcard characters. Apply every filter within the existing user/project/archive scope before counting and pagination. Defaults, latest parsing-task links and GitHub provenance remain unchanged. Status filters describe the source record, separately from task status.

The frontend submits filters explicitly, resets to page one, discards stale responses and resets filters when switching projects. Language options reuse the frontend upload registry; the backend validates its own authoritative registry. Preserve an already opened source even if it is absent from the current page or filtered results, and explain that state. Filtering does not parse, extract, review or call providers.

Store the requested page separately from the last displayed response so errors retry the failed page. If a successful response shows that the requested page no longer exists, request the last valid page. Apply-filter focus moves to the source-list heading only while the project and applied filter identity still match. Existing operation locks also disable filters and list actions.

## Consequences

Users can find imported notes/code and inspect parsing failures without manually paging through every file. No full-text content search, repository filter, automatic retry loop, migration or new dependency is introduced. Existing evidence navigation can open a source independently of list filters; this changes neither stored source identity nor authoritative knowledge.
