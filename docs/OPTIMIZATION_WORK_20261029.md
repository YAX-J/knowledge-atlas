# Ordered optimization work · 2026-10-29

User authorizes implementing the P0/P1/P2 sequence from the project review and Agent verification. Real human grading is deferred by the user; never fabricate scores. Public-only provider budget remains cumulative 120 model /160 embedding attempts (84/61 already spent); preserve the existing ledger. No push or publication.

- [x] P0: schema-aware readiness; 19-table backup/recovery verified; application upgraded to 0018 and 18 existing business-table content hashes preserved under UTC comparison. All five existing project graphs readable. Native end-to-end workflow passed with provider stubs. Backup/report remain ignored output.
- [x] P1: explicit immutable compiler snapshot/version selection and repeated-path regression, including old commit paths after rename and scope refusal.
- [x] P1: normalized identity bounds, merge-chain/alias/unmerge retrieval regressions passed.
- [x] P1: critical frontend integration tests and broader honest coverage (108 tests; conversation page 90.47% lines, useConversations 97.82%; expanded overall denominator).
- [x] P1: new separate frozen 7-document/24-question holdout-v3 and human-review handoff (real grades explicitly deferred by user).
- [x] P2: URL navigation/context restoration and shorter task paths, including external-page projects and foreign source refusal.
- [x] P2: 1k/10k scale measurement, bulk index evidence, latency/memory/request-cost accounting. Plan SQL1002/10002→4/22, p95 837.236/8914.231→103.809/1033.329ms; identical fingerprints, linear memory,0 providers.
- [x] P2: extract App orchestration into evidence/snapshot/evolution modules; consolidate current bilingual docs and archive historic checkpoints with corrected links. Preserve original nine orchestration regressions and put new tests in a separate file.
- [x] Final focused/full/native/browser checks: backend713 passed/7 skipped94.97%; native135 passed plus migration roundtrip/cleanup; frontend108 passed,72.54% configured lines; production build passed; desktop native/stub walkthrough passed. JSON DISTINCT incompatibility found natively and fixed before final reruns.
- [x] Final whitespace/link/frozen-byte/staged review passed. Exact staged v3 fingerprint matches3215df76dd621e2fe8c9a7bc60fe640d6d7d171fe8be141b061f067fe12d1801; original orchestration regressions unchanged. Pinned upstream EOF blank lines are preserved with a corpus-only Git whitespace attribute. Local commit closes the turn; no push.

Cleanup: both recorded browser schemas absent; native/scale runners removed their owned schemas. Named Chrome session closed, dedicated8010/5180 ports released. Application marker remains0018. No backup/output/dependency/secret artifact staged.

Verification: existing backend venv, frontend dependencies, native PostgreSQL/pgvector and SDKs. Agent runs focused then full pytest with 90% app coverage, native disposable-schema migration/workflow checks, npm run test:coverage/build, desktop Chrome walkthrough, and git diff --check. Back up application data before upgrade; never downgrade business data or clean unrecorded schemas.
