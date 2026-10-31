# ADR 0075: Derive aggregate answer support on the server

[简体中文](0075-server-derived-answer-support.zh-CN.md)

- Status: Accepted
- Date: 2026-10-31
- Supersedes: ADR 0069's provider-generated aggregate `supported` field only. Claim attribution, evidence scope, persistence and human-review boundaries remain.

## Decision

Use `evidence-claims-v3` for new answers. The provider must return exactly `confidence`, `claims` and `missing_information`. `ClaimAnswerDraft.supported` is a server property: true exactly when every claim has status `supported`. At least one claim is required. The property is absent from provider JSON Schema and serialization; a provider-supplied aggregate is rejected as an extra field, even when consistent. Both single_step and tools parse this schema without fallback or automatic retry.

The API continues to return `supported`, flat `answer`, evidence and entity IDs. Mixed answers retain supported claims and their exact citations, with overall false; wholly insufficient answers have no citations. Insufficient claims still require missing information. Per-claim citations, unique UUIDs, current retrieval/project scope, claim/text/citation limits and strict unknown-field validation remain mandatory. These checks establish structure and attribution, not semantic entailment.

Keep stored v2 and flat responses unchanged. `QuestionRead` accepts both version strings plus null; reads and same-UUID replay neither recompute support nor call providers. `ClaimAnswerDraftV2` remains an explicit strict historical diagnostic adapter, never a live parsing fallback. No SQL migration is needed; head remains `20261029_0019`. New experiment manifests record v3; exact reuse rejects a v2 scope instead of relabeling it as v3.

## Validation boundary

Develop against [independent fictional Nimbus cases](../../evaluation/development/claim-support-v3/README.md): all supported, mixed, all insufficient and shared citations, plus adversarial mutations. The fixture contains no frozen corpus, question IDs, failed answer text or judge feedback. HTTP substitutes exercise both provider paths and verify one attempted request with no retry on rejection. Integration tests cover cross-project citations, empty evidence, persistent history/replay and evaluation exports.

Historical experiments, holdout-v3, provider grants/ledgers, raw outputs, metrics, exclusions and judge reports remain byte-for-byte unchanged. Their v2 invalid outputs remain invalid and ungraded. The historic five aggregate mismatches are motivation to remove a redundant representation, not five repaired experimental samples. This change does not authorize a new live run, infer an improved success rate or establish v3 model quality. Human grading remains 0%.

## Consequences

The model no longer has to reproduce a deterministic aggregate. It can still emit inconsistent claims, unsupported text or malformed JSON; strict rejection remains. A future model-quality comparison needs separately authorized development evaluation and new versioned artifacts. Frozen v2 results must always be identified as historical v2 results.
