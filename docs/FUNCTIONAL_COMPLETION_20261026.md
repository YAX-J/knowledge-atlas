# Functional completion acceptance · 2026-10-26

[简体中文](FUNCTIONAL_COMPLETION_20261026.zh-CN.md)

This change addresses the seven functional/research rows of the completeness review. Engineering/deployment expansion is excluded. “Implemented” below refers to the stated context; external acceptance is listed separately.

| Area | Delivered behavior | Acceptance boundary |
| --- | --- | --- |
| Import | Fixed-commit file continuation, cached full manifests, resumable directory frontier when GitHub recursive trees truncate; sequential local folders up to 10,000 supported files | 50 downloads / 20 MiB per request; 10 directory reads per step; 250,000 manifest entries / depth 64; a truncated individual directory is explicitly blocked, with local folder fallback. Private token acceptance pending |
| Identity | Reasoned aliases, NFKC/casefold collision checks, same-type manual merge/unmerge, temporal canonical graph/search/evidence/vector projection | No LLM identity writes; original UUIDs/evidence/edges preserved; at most 1,000 merged members per canonical identity |
| Time | Withdraw confirmation, reactivate, preserve historical validity gaps, atomic 1–10 old × 1–10 new replacement groups, reverse an independent linear replacement | A group is an explicit complete old/new replacement, not arbitrary per-pair matching. Cycles and dependent reversal are refused; no retroactive audit erasure |
| Questions | Project-scoped persistent conversations and paginated turns, six-turn context, fresh evidence and citation validation, request idempotency and execution fencing | 200 turns per conversation; context is a hint, never evidence. Unknown/failed execution requires explicit paid retry |
| Code | Python/JS/TS import aliases; explicit Java JDK 17, TypeScript checker, Go same-package compiler analysis, including declarations outside outline candidates | Static declaration resolution only; no build scripts, emit, processors or user execution. Missing dependency/classpath diagnostics remain visible. C/C++/C# retain bounded syntax/Agent paths |
| UI | Real workbench counts, top navigation, contextual header search, persistent conversations, named identity/lifecycle previews and audits, continuation controls | Default is real workbench; demo is explicit. The separate prototypes remain reference artifacts |
| Research | New pinned public corpus, online answer comparison, two independent extraction runs, public code-call positive checks, offline blind review and charts | Agent-authored gold; no independent human grades or representative full-repository benchmark claimed |

Migration head is `20261026_0018`. It adds six tables and nullable `repository_snapshots.scan_state`; no existing knowledge is deleted or rewritten by upgrade. Downgrade removes the new audit/history/conversation data and must never be used as a business-data repair shortcut. Native migration round trips ran only in disposable schemas. Application migration state and final verification are recorded in [work log](COMPLETENESS_WORK.md).

Verification: final full backend regression passed **704 tests, 7 skipped, 94.88% app statement coverage**, including all three actual compilers. Native PostgreSQL 17.10 / pgvector 0.8.7 migration round trip and **129 functional tests** passed, then removed its own schema and verified the application's migration marker unchanged. Frontend **93 tests**, type checks and production build passed; measured coverage is 71.94% statements / 76.93% lines in the configured scope. No Docker or remote CI claim is made.

Desktop walkthrough used a separate Chrome session at 1440 × 1100, frontend port 5180 and API port 8010, with a disposable schema and provider stubs. Checked real counts/navigation, Ctrl+K project search, evidence/line links, aliases and audit, conversation persistence/reload, synthetic Markdown upload → parse → extract → named batch review → graph. Screenshots are ignored local output, never private inputs. The public research calls used real providers separately.

The public evaluation used **84 model / 61 embedding attempts cumulatively**, within the user's 120/160 cap. Failed and unknown calls count against the ledger; no private text was sent. See the [public report](../evaluation/results/2026-10-26-public-v2-run1/REPORT.md). Private repository acceptance requires a repository and configured authorization. Human correctness/explainability remain missing until real reviewers submit the blank blind-review form. Broader compiler build contexts and full repositories remain future validation, not solved by model confidence.
