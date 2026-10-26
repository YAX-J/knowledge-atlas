# ADR 0057 Grounded persistent conversations and measured defaults

[简体中文](0057-grounded-persistent-conversations.zh-CN.md)

- Status: Accepted
- Date: 2026-10-26

## Decision

Persist scoped conversations/turn snapshots. Serialize lease claims, release transactions before network, and fence publication with a separate execution UUID. Keep at most six prior turns as untrusted hints; retrieve and validate fresh evidence every turn. Use request UUID for successful idempotency; failed/unknown requests require explicit retry. Bound each conversation to 200 turns. The public-v2 preregistered evidence Recall@5 selects RRF as question default; retain explicit mode choice and keyword search API compatibility.

## Consequences and alternatives

This extends ADR 0011/0045. Prior answers are not evidence. The paired RRF-vector interval includes zero; agent-authored gold and zero human coverage prohibit a general semantic-quality claim. Future tuning needs new independent data.
