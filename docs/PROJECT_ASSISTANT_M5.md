# Project assistant M5: offline acceptance and quality preparation

[简体中文](PROJECT_ASSISTANT_M5.zh-CN.md)

Status: **offline preparation implemented; M5 overall is not complete**. Product baseline:`e0998c4`, schema:`20261031_0023`. See [ADR0080](adr/0080-project-agent-development-acceptance.md) and the [independent packet](../evaluation/development/project-agent-m5-v1/README.md). This phase adds no business migration, API, dependency or UI change.

## Repeatable engineering acceptance

Reuse `backend/.venv`, `frontend/node_modules` and native PostgreSQL with pgvector. The user's existing Agent verification selection persists. From `backend/` run:

```powershell
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 validate
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 acceptance --full --native --frontend --output ../output/m5-acceptance-new
```

Output must be a **fresh child** of repository `output/`; existing directories are refused. The command saves its plan before executing, then runs focused regressions, full backend90% coverage, native isolated migration/regressions, frontend coverage and production build. Omit optional flags for a focused-only run. Failure stops later stages; there is no automatic rerun or continuation. Inspect `engineering.json`, per-stage logs/hashes, JUnit XML and coverage artifacts. Failures/pending stages remain visible.

The18-entry matrix binds real test functions for scope/time/version rejection, malicious input, exact citations, no evidence, unknown attempts, checkpoints, cumulative budgets, progress loss, notes, approval, governance, import, cancellation, identity changes, specialist accounting, long notes, migration and separate-transaction fencing. Additional fictional-corpus smoke checks cover actual quote production, old-note attachments, injected write attempts, rejection, concurrent edits, wrong actors, modified proposals, duplicate decisions and wrong returned commits. These tests are engineering checks, not the20 quality-task results.

`scripts.m5_offline` blocks real sync/async HTTP transports. ASGI and explicit HTTP mocks remain usable. The full and native runners propagate this barrier, refuse real public GitHub acceptance and retain existing thresholds. Native acceptance checks physical table ownership, tests upgrade/downgrade in its own generated schema and removes that schema; it does not migrate or downgrade business data. Desktop evidence is the M3/M4 baseline and is explicitly marked not rerun because M5 changes no UI.

CI definitions validate the packet and archive a zero-call preflight; backend/native jobs enable the transport barrier. A local run or edited workflow is not a green hosted workflow. No push or remote workflow trigger is included in this task.

## Frozen20-task development packet

The packet has evidence, organization, code, notes and governance categories, four tasks each, with11 new fictional materials. Inputs, scopes, allowed actions, operator steps, expected outcomes, citation anchors and rubric are sealed before real model evaluation. The SHA-256 is `1b7759bc8acb503b6541ea4711c6ca0ccec8f4fdd757782090fc62efa9e42d9b`. Trusted code verifies each sealed file and the overall digest. New packet versions are required for later revisions.

Each quality task needs an independently prepared isolated project. G01 uses a local snapshot/HTTP substitute even in a future real-model run; real GitHub behavior is a separate acceptance claim. Historical fixture replay uses a test clock, not a backdating API. G02 keeps both policy endpoints active until current-time review. The declared operator steps are required interactions, not an automatic approval policy. The current tool deliberately provides **no live executor or isolated quality-fixture replay implementation**; these are concrete next work before authorizing a live run.

```powershell
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 preflight --output ../output/m5-preflight-new
# Optional smaller explicitly selected plan:
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 preflight --task E01 --task N03 --output ../output/m5-preflight-subset-new
```

Preflight reads the locally configured task model and stores an endpoint fingerprint, never credentials. It records product/tooling fingerprints, exact task selection and schema/protocol. All20 tasks cap at160 total model attempts and320 tools,0 embeddings,0 judges; each task shares8 model/16 tool attempts across roles. Reservations/completions remain0. Authorization is null and `live_execution_allowed=false`. Monetary estimates and returned model snapshots remain unverified. This document/preflight does not authorize paid calls. Do not reuse any historical grant.

## Import and assess future reported results

Preserve the original task GET JSON. A reported-run JSON has `protocol=project-agent-reported-run-v1`, packet/preflight SHA-256, `source_mode=substitute|externally_reported_live` and an observations array. Each attempted task has:

- `case_id`, original `task` JSON (or null with `failure_code` after an unavailable export), and reported `elapsed_ms`.
- `material_ids`: symbolic fixture material IDs mapped to the actual scoped source/revision UUIDs. Include materials actually cited; raw attachments and formal evidence remain distinct.
- `safety_findings`: explicit operator-reported violations, or an empty list. Empty is not independent certification of safety.

Cases omitted from observations are listed as not attempted. Duplicate/out-of-plan records are rejected. The importer checks task protocol/goal, selected source/note versions, hashes, capabilities, time, budgets, result reference IDs and exact excerpt provenance. Invalid exports remain in attempted counts rather than disappearing. This is a reported-data adapter; it cannot independently prove the origin of supplied files or a provider run.

```powershell
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 review-template --preflight ../output/m5-preflight-new/preflight.json --reported-run path/to/reported-run.json --output ../output/m5-review-new
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 assess --preflight ../output/m5-preflight-new/preflight.json --reported-run path/to/reported-run.json --output ../output/m5-summary-ungraded-new
# Add --grades path/to/completed-grades.json only after explicit task-specific review.
```

The template contains no grades: `grades=[]`, with null placeholders under `ungraded`. Keep unfinished rows there; place only completed reviews under `grades`. Each grade binds case ID, exact observation/run hashes, reviewer ID/kind, completion,0–4 factuality/completeness/citation-support, uncertainty and rationale. Human/model scores and coverage stay separate. The existing answer judge is not automatically invoked and is not a general write/recovery/task judge.

Report all attempted tasks as the primary denominator, including failures, interruptions and pending review. Report structurally valid and graded subsets separately. No grading yields null completion/semantic metrics; partial grading yields a confirmed-completion lower bound, not an invented full completion rate. Server `succeeded` is a technical status. Correct clarification, missing evidence, rejection and conflict may satisfy the specified task. Preregistered exploratory thresholds are completion≥80%, semantic means≥3/4, citation support≥3.5/4 and zero reported safety violations, with full attempted grading coverage. A subset gate is explicitly separate from the full20-task gate. Assess always returns `release_status=not_certified`.

## Release and graduation checklist

| Gate | Current evidence / remaining work |
| --- | --- |
| Local engineering | Run the unified command and retain its actual stage results; see verification record below |
| Data recovery | M3/M4 verified31-table backup/restore and30 preserved old-table fingerprints remain the baseline; M5 adds no migration |
| Hosted Linux/container CI | Pending a separately authorized push/new-commit workflow; no local substitute for this result |
| Real task quality | No live requests, no real task outputs and no semantic grades in this phase; prepare the executor/replay then obtain a concrete scoped grant |
| Final quality | Fresh tasks after debugging; preserve the development set and all historical experiments |
| Operator review | Every exact write proposal needs review; simulated decisions do not count as human evidence |
| Demonstration | M3/M4 screenshots exist locally; prepare/record a deterministic full-task demonstration and label substitutes |
| Delivery | Start API, parsing worker, assistant runner and frontend; document unknown-result recovery, budgets, approval and backup paths |
| Publication | Local single-user candidate only. Real authentication/deployment hardening and explicit tag/publish/deploy authorization remain separate |

Demo runbook: create a note, autosave, attach its revision, produce a cited report; edit the note and reopen the old citation; request an existing-note change, inspect/reject a proposal; then use a new task to import the pinned local snapshot, parse/extract, inspect exact candidate/evidence, explicitly approve/continue and open formal citations. Record task IDs, versions, counters and the provider substitute label. Do not imply source inspection is a successful runtime test.

## Verification record

Actual Agent-run verification on2026-10-31: initial packet/flow focus36 passed. The unified run then passed105 focused/2 skipped, full backend1103/13 skipped with95.55% app coverage (90% gate), native PostgreSQL306, frontend156 with71.60% statements/76.20% lines and production build. Native schema cleanup and unchanged business migration marker passed. After the full run, one scoring guard rejects complete=true for failed/interrupted/waiting/cancelled/queued/running states; the final focused run passed111/2 skipped and its implementation hash matches the zero-call preflight. Product runtime/UI/schema sources did not change. Hosted CI remains unrun.

The actual local command outputs live under ignored `output/m5-acceptance-20261031-01/`; the final reviewed focus is under `output/m5-acceptance-final-20261031-01/`. Live provider requests, embedding/judge reservations and human grading remain0. Existing frozen inputs/results/grants/ledgers are preserved. M5 overall remains pending quality, hosted CI, demonstration and release gates.


Concrete zero-call artifacts: `output/m5-preflight-20261031-01/preflight.json` uses configured `deepseek-flash`,160 model/320 tool maximum,0 embedding/judge,0 reserved/completed and no grant. CLI review/assessment on an empty input reports0 attempts/20 not attempted, null quality metrics and human coverage0; it is not a task run. These records live under `output/m5-review-empty-20261031-01/` and `output/m5-summary-empty-20261031-01/`.
