# Ordered optimization acceptance · 2026-10-29

[简体中文](OPTIMIZATION_20261029.zh-CN.md)

Implemented the user's ordered P0/P1/P2 list. The user explicitly chose Agent verification and deferred real blind grading. No new provider calls, push or deployment occurred. ADR 0060–0063 specify the new boundaries. Earlier reports retain their original results.

## Delivered behavior

| Priority | Outcome and evidence |
| --- | --- |
| P0 runtime | Backed up 19 old tables; verified schema restore; upgraded the application from0017 to0018 after matching pre-upgrade fingerprint. UTC-normalized content hashes of all18 old business tables match; new snapshot scan_state excluded from old-row comparison. Five existing project graphs and schema readiness read successfully. Backup/upgrade report remain ignored local output. |
| P0 guard | Connectivity and actual schema head/critical structures checked separately. Unmigrated, behind and falsely stamped databases refuse readiness. No startup auto-migration. End-to-end upload/parse/stub extraction/explicit review/index/search/conversation/evidence regression included in native runner. |
| P1 analysis | New context descriptor and fixed snapshot/local one-version-per-path selection before every strategy. Reused source, old commit after rename, same-path versions, foreign contexts and metadata-before-body limits covered in SQLite and PostgreSQL. Native testing caught JSON DISTINCT incompatibility; membership subquery fixes it. |
| P1 identity | NFKC/casefold length expansion, blank/NUL, alias conflict, A→B→C flattening and retrieval ownership after unmerge. Original evidence remains attached to original owners. |
| P1 frontend | Mounted timeout/inspection/explicit retry, saved/paginated conversation, dependency review, historical write refusal, named confirmation, project/time round trips, late requests and disposal. Existing tests preserved; new extraction tests have a separate file. |
| P1 data | Seven genuine fixed-commit MIT upstream technical documents;24 new questions (8 direct/8 cross-document/4 temporal/4 unanswerable),19 curated entities. v1/public-v2 development versus frozen v3 test. No v3 provider run or real human score. |
| P2 navigation | Hash URLs restore project/source/entity/relationship/time/conversation and task section. Works for projects outside the first list page; foreign source links refuse. Graph sections shorten the path to relations/search/identity/evolution/retirement. |
| P2 performance | Batches of500 evidence owners; existing embedding metadata projection and UUID plans. Native1k/10k benchmark,20 warm samples, before/after identical plan fingerprints, SQL/p95/Python allocations and hypothetical batch counts. |
| P2 maintenance | `useEvidenceNavigation`, `useRepositorySnapshots`, `useKnowledgeEvolution`; latest request/disposal fencing retained. Root capabilities/plans/frontend rewritten around current behavior; previous text archived with corrected relative links. Paired ADR/docs and seven local skills synchronized. |

## Measured change

| Entities | Index-plan SQL | Plan p95 ms | Python peak MiB |
| --- | --- | --- | --- |
| 1,000 | 1,002 →4 | 837.236 →103.809 | 2.69 →2.78 |
| 10,000 | 10,002 →22 | 8,914.231 →1,033.329 | 23.63 →23.67 |

See [raw samples and scope](../evaluation/performance/2026-10-29-scale/README.md). Improvement is in planning query count/latency; memory remains linear. No provider transport/vector persistence was measured. BM25 keeps the explicit1k scan window and truncation. Cold batch32 request estimates are32/313 for1k/10k, actual requests0. No price is invented; this is not authorization for313 paid calls. No ANN/cache added without representative vector and invalidation measurements.

## Verification actually run

- Backend: `KA_NATIVE_COMPILERS=1` plus `python -m pytest --cov=app --cov-fail-under=90 ... -ra`: **713 passed,7 skipped;94.97%** app statement coverage. Skips are the explicit live GitHub opt-in and six native-only cases; the native runner executes those native cases separately. One existing transport deprecation warning remains.
- Native: `python -m scripts.verify_native`: **135 passed**, migration upgrade/downgrade/upgrade, physically owned disposable schema removed, application marker unchanged. Includes offline v3 replay validation as well as native business checks.
- Frontend: `npm run test:coverage`: **108 passed /15 files**; configured scope statements67.64%, branches60.58%, functions49.01%, lines72.54%. Conversation page lines90.47%; useConversations lines97.82% /branches84.34%; route module lines100%. Scope now includes App/API/extracted modules; not comparable to old narrow-scope percentages.
- `npm run build`: type check and production build passed.
- Desktop Chrome via agent-browser: actual API/native temporary schemas, public fixture/local provider stubs. Verified task-section reload, historical read-only controls, saved conversation/answer after reload, exact evidence chunk focus/highlight, browser back, source URL restore, analysis-context availability, keyboard focus and no horizontal overflow. Error/empty/retry states also have mounted regressions. No mobile test or real-model-quality claim.
- Native scale benchmark: both sizes completed,20 samples per path, identical plan fingerprints, zero providers, temporary schemas removed.
- Final whitespace/staging/link/frozen-byte checks recorded in the work log before local commit. Backups/output/dependencies/secrets are excluded from tracked deliverables.

## Deferred work and limits

The user will fill [the existing80-row blind review](../evaluation/holdout-v3/README.md). No grades fabricated. Personal technical notes were not provided: v3 uses genuine public documentation. Upstream FastAPI overlaps public-v2's framework, so the new document/question split is not an unseen-repository/domain test. Agent-authored gold requires independent review; temporal replay replaces document snapshots, not actual API validity or personal-note chronology.

V3 fingerprint: `3215df76dd621e2fe8c9a7bc60fe640d6d7d171fe8be141b061f067fe12d1801`. Do not tune ranking/prompts/thresholds on it. Future experiments use new result directories and the cumulative ledger: authorization120 model/160 embedding attempts, already84/61 spent, **this turn0/0**.

Private-repository authorization, privileged fresh-database restore, Docker and remote CI still require their actual environment. Compiler analysis remains bounded static identity without full build dependencies/runtime semantics; URL restore does not save unsent forms or analysis selections. These limits are stated in current documentation.
