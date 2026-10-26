# ADR 0056 审计身份与历史生效区间

[English](0056-audited-identities-and-validity.md)

- Status: Accepted
- Date: 2026-10-26

## Decision

新增 EntityAlias/EntityMerge/KnowledgePeriod/KnowledgeOperation。人工操作在项目锁下幂等执行，保留原 UUID、证据和边，读取时按时间投影。向量只保存原拥有者文本，避免当前合并污染历史。重新启用前保存闭合区间。分组替代必须同类型、原子、无环且最多 10×10；仅无依赖的线性替代可单独撤销，不改写旧审计。

## Consequences and alternatives

不采用物理破坏性合并，避免丢失来源与历史；模型不能自主确认身份。降级会移除新历史，须备份，不能充当撤销业务操作。
