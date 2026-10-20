# ADR 0020: Derive immutable GitHub evidence links from snapshots

[简体中文](0020-derived-immutable-github-evidence-links.zh-CN.md)

- Status: Accepted
- Date: 2026-10-20

## Context

Formal evidence already has a stable internal `project://` locator and exact source lines. GitHub imports also persist commit and per-file snapshot provenance, but users cannot open the corresponding immutable remote text. Linking to a branch would make old evidence drift as the branch advances, while copying a GitHub URL into every evidence row would duplicate derived provider data and require a migration.

## Decision

Source list/detail responses derive a nullable `git_url` from the latest non-deleted snapshot-file occurrence for that source. Formal graph, search, and question evidence derive the same commit-pinned file URL and append GitHub's one-based inclusive line fragment. Paths are URL-encoded while `/` separators are retained.

The persisted `project://` URI remains the canonical application-local locator. `git_url` is an optional external convenience link and is not stored on sources or evidence. Local sources and imported sources without usable snapshot provenance return `null`. If a remote file is later deleted, its source and evidence resolve to the last snapshot in which that source still occurred. Repository coordinate changes use the current canonical GitHub remote together with the historical commit SHA and path.

## Consequences

- Evidence opens at an immutable commit and exact line range rather than a moving branch.
- No schema migration or evidence rewrite is required; snapshot history remains the source of truth.
- Source pages, graph details, search results, and question citations expose the same provenance behavior.
- Private-repository links still require the browser user to have GitHub access; backend tokens are never placed in URLs or responses.
- Force-push reachability, automatic evidence invalidation, Issues, Pull Requests, and non-GitHub providers remain out of scope.

## Alternatives considered

- Link to the default branch: rejected because evidence would drift.
- Persist a URL on every source/evidence row: rejected because it duplicates snapshot-derived data and complicates repository renames.
- Remove `project://` in favor of GitHub URLs: rejected because local sources and application navigation still need a provider-independent locator.
