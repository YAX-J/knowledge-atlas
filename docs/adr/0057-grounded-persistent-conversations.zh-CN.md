# ADR 0057 证据约束的持久化会话与实测默认策略

[English](0057-grounded-persistent-conversations.md)

- Status: Accepted
- Date: 2026-10-26

## Decision

保存隔离会话与轮次快照；短事务领取租约，网络前提交，独立 execution UUID 隔离过期执行。最多六轮历史只作不可信提示，每轮重新检索校验引用。成功请求 UUID 幂等，未知/失败需显式重试，每会话最多 200 轮。按 public-v2 预声明证据 Recall@5 将问答默认改为 RRF，保留显式模式与 keyword 搜索 API。

## Consequences and alternatives

扩展 ADR 0011/0045；旧回答不能作为证据。RRF 与向量差异区间含零，Agent 金标、人工覆盖率零，不能声称普遍语义优势。未来调参需新独立数据。
