# Core functional acceptance — 2026-10-23

[简体中文](CORE_ACCEPTANCE.zh-CN.md)

Scope approved by the user: Stage 4 bounded code/GitHub core, Stage 5 temporal/governance, then integration. Public GitHub reads were authorized; real model/embedding calls were explicitly deferred. This is functional acceptance, not a claim that all graduation experiments or provider quality are complete.

## Evidence

| Criterion | Result and reproducible coverage |
| --- | --- |
| Repository file/symbol lookup and exact source | `tests/test_stage_four_workflow.py`: 40-file fixture, exact symbol/chunk UUID and line navigation, repeat upload/parse preserves source/chunk counts, no automatic formal knowledge |
| Real public source import | `python -m scripts.verify_native --github`: spring-petclinic commit `500158f732419217507c7656904b8e6aa1bcc0d6`, 30 sources / 301 chunks; configured 30-file budget and `truncated=true`, not whole-repository coverage |
| Public code provenance | [PetClinicApplication lines 28–36](https://github.com/spring-projects/spring-petclinic/blob/500158f732419217507c7656904b8e6aa1bcc0d6/src/main/java/org/springframework/samples/petclinic/PetClinicApplication.java#L28-L36) matched the original symbol/chunk; repeated pinned synchronization did not add sources/chunks; saved commit-message import reused its source |
| Decision/evidence promotion | Existing `test_commit_sources.py`, `test_graph.py`, `test_knowledge.py`: explicit extraction fixtures → human review → formal knowledge and exact source/commit evidence; not real model-quality assessment |
| Replacement history and present state | `test_evolution.py`: reviewed three-version chain, old→new cutover boundary, current/historical graph/search/detail visibility, incident edges hidden currently but retained historically |
| Review safety | Evidence revalidated at confirmation, stable identical-request UUIDs, same-action idempotency, stale/cross-scope/archived/invalid-time rejection, no reversal/fork/merge/cycle; reject does not mutate knowledge |
| Governance | Deterministic read-only missing-evidence, same-name duplicate/possible-conflict and orphan suggestions; no automatic candidates or writes; bounded scan/results/history and explicit truncation |
| Native PostgreSQL | PostgreSQL 17.10 / pgvector 0.8.7: all 29 opt-in tests passed, migration empty→head→0014→head, independent-session upload/proposal/confirmation races, competing successors and abandoned Worker fencing |
| Desktop UI | Chrome 1440×1100, disposable SQLite fixture: empty states, keyboard proposal/second confirmation, three-version chain, historical search and exact chunk focus, long names, scroll, network error/retry; new evolution region axe 22 passes / 0 violations / 0 incomplete after fix |
| Build/regression | `npm run build` passed. Final ordinary pytest: 488 passed / 4 opt-in native/public tests skipped / 1 existing Starlette deprecation warning (31.42 s). Native/provider results above are separate from SQLite regression. |

## Native isolation incident and recovery

The first native harness incorrectly relied on `search_path=temp,public`, allowing Alembic/version and business-table fallback. It created four synthetic projects and advanced the public marker. This run was rejected as an isolated acceptance result. The user explicitly approved restoring only the four identified fixture UUIDs and this run's empty-column/migration changes; a guarded single transaction checked developer user, timestamps, exact synthetic text/hashes, and removed only those fixtures. The original business revision `20261021_0013` was restored; existing business content was preserved. Synthetic fixture deletions have no backup but are reproducible.

The corrected harness explicitly sets `version_table_schema`, verifies all local core tables plus an initially empty project table before tests, and checks the public marker after cleanup. Subsequent native runs passed with a fully created temporary schema and no public marker change. Never use a business schema for downgrade acceptance or fixture cleanup. Downgrading `0015` loses change/audit records without undoing entity validity; back up before any business migration.

## Boundaries and next service step

- No real model/embedding invocation in this round, per user choice; no private-token/thread authorization acceptance, automatic polling/webhooks, full Java compiler semantics or automatic semantic conflict judgment.
- Supplement/conflict confirmation records classification only; replacement is linear and cannot be dated before both endpoints' current validity starts or into the future. History is separate from one-hop semantic retrieval.
- Experiment datasets, quality metrics, entity merging/disambiguation, question history and multi-turn behavior are not claimed complete.
- Apply `alembic upgrade head` to the actual service only after backing it up and choosing to upgrade. Disposable acceptance never upgrades the business schema. Current code head is `20261023_0015`.
- Generated screenshots, native metadata and backups belong under ignored `output/`; do not commit original imported bodies, credentials or database dumps.
