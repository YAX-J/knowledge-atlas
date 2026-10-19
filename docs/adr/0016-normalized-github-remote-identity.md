# ADR 0016 Normalize GitHub remote identity before repository import

[简体中文](0016-normalized-github-remote-identity.zh-CN.md)

- Status: Accepted
- Date: 2026-10-19

## Context

Local-folder names provide a repository boundary but cannot identify the same repository across machines or support later GitHub import. Importing remote content before defining canonical identity would risk creating a second repository record for a folder that already represents the same codebase. Storing arbitrary clone strings would also retain credentials or treat HTTPS and SSH forms as different repositories.

## Decision

- Extend `source_repositories` with nullable `provider`, `remote_owner`, `remote_name`, and canonical `remote_url` fields. Existing local repositories remain valid with all four fields null.
- Support `github` as the first provider and `git_remote` as the remote-only repository kind.
- Resolve identity through `POST /projects/{project_id}/repositories/resolve-github`. Accept GitHub HTTPS, SCP-style SSH, and `ssh://` remotes; reject other hosts, query strings, fragments, and credential-bearing HTTPS URLs.
- Normalize owner and repository names to lowercase and store `https://github.com/{owner}/{repository}` as the canonical URL. Identity is unique within the current user and project by provider, owner, and repository name.
- Optionally attach the identity to an existing unlinked `local_folder` repository. Without a local repository ID, create or reuse a remote-only repository record.
- Serialize resolution with the project-row lock. Do not contact GitHub, validate repository existence, request credentials, clone files, or infer a default branch in this slice.

## Consequences

The project now has one repository UUID that future GitHub source import can reuse, including when a local folder is explicitly linked first. Equivalent supported HTTPS and SSH strings resolve idempotently. Conflicting links return explicit HTTP 409 errors instead of silently merging repository records.

This identity is still weaker than a GitHub provider repository ID: renames and ownership transfers are not detected, and lowercased owner/name coordinates remain the key. Remote registration does not prove that the repository exists or is accessible. Branches, commits, file retrieval, deletion reconciliation, webhooks, and tokens remain future work.

Downgrading migration `20261019_0009` to `0008` removes remote metadata from linked local repositories and deletes remote-only `git_remote` records because the previous schema cannot represent them. It does not delete local repositories or their sources.

## Alternatives considered

- Store the submitted remote string unchanged: rejected because equivalent HTTPS/SSH forms would diverge and credential-bearing URLs could be persisted.
- Call GitHub immediately and use its repository ID: deferred until authenticated/public GitHub ingestion is implemented.
- Automatically merge an existing local and remote-only record: rejected because moving sources between repository boundaries changes deduplication and cross-file resolution semantics.
