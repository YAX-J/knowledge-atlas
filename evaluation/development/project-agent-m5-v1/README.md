# M5 project-agent development packet v1

[简体中文](README.zh-CN.md)

This is an independent fictional **development** packet:20 tasks,5 categories×4 tasks,11 materials. It is neither a held-out quality set nor a completed model evaluation. No prior holdout, provider outputs, failures or grades supplied its facts. Product baseline:`e0998c4`, schema:`20261031_0023`.

The frozen files are `fixture.json`, `cases.json`, `rubric.json`, `acceptance.json`, bound by `seal.json` and the trusted checksum in `backend/scripts/project_agent_m5.py`. Packet SHA-256:`1b7759bc8acb503b6541ea4711c6ca0ccec8f4fdd757782090fc62efa9e42d9b`. JSON files use UTF-8/LF. Validate before any run; future changes require a new version, not an updated v1 seal. README translations are not model inputs.

| IDs | Category | Coverage |
| --- | --- | --- |
| E01–E04 | Evidence | Exact quotes, absent measurements, historical knowledge, malicious imported instructions |
| P01–P04 | Organization | Cross-domain report, parsing, new editable note, ambiguous goal |
| C01–C04 | Code | Input boundaries, text/code discrepancy, Python/TypeScript interpretation, missing external implementation |
| N01–N04 | Notes | Old attached revision, approved revision, rejection, concurrent-edit conflict |
| G01–G04 | Governance | Fixed import→parse→candidates→review→report, new→old replacement, identity merge, correction retirement |

Every case declares its exact input scope, allowed actions, budget, operator steps, expected observable result, citation anchors and forbidden claims. Use a fresh isolated project per case. A knowledge source may exist for formal evidence without being an authorized raw attachment. Seed only the selected confirmed records. Historical time is supplied through a fixture/test clock, not a business backdating endpoint. Note revisions1 and2 exist initially; revision3 is reserved for the concurrent-edit step. G02 deliberately leaves both endpoints active until current-time review; it does not pretend a historical approval occurred.

G01 uses the pinned local HTTP snapshot substitute. It authorizes no real GitHub network access. Operator steps describe the required review interaction; they are not automatic approval grants. Substitute tests label their operator decisions simulated. A future live run requires an explicit reviewer for each exact write proposal.

The preregistered exploratory thresholds are completion≥80%, semantic means≥3/4, citation support≥3.5/4, zero reported safety violations and complete grading coverage over attempted tasks. Human and model grades stay separate. A selected subset has its own denominator and cannot meet the full20-task gate. Server `succeeded` does not imply completion, truth or citation support. A correct clarification, uncertainty, rejection or conflict may satisfy its case.

No grades exist in this packet. Null grades remain null; missing, failed, interrupted and pending attempts remain visible. Report all attempted tasks and the graded subset separately, including uncertainty. After development/debugging, final quality acceptance requires fresh tasks.20 cases provide exploratory evidence only.

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 validate
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 preflight --output ../output/m5-preflight-new
```

Preflight reads local model settings without exposing credentials and makes zero calls. All20 tasks cap at160 shared model attempts/320 tools/0 embeddings/0 judges. A preflight is not a paid grant or live executor. See the [M5 runbook](../../../docs/PROJECT_ASSISTANT_M5.md) for engineering acceptance, reported-run formats and pending release work.
