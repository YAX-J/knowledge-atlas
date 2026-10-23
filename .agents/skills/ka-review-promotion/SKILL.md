---
name: ka-review-promotion
description: Knowledge Atlas 的候选审核与正式图谱写入。确认/拒绝候选、补写旧候选、修改图谱查询或证据展示时使用。触发词：review, confirm, reject, promote, graph, entity, relationship, SUPERSEDES, 审核, 确认, 图谱.
---

# 审核与正式图谱写入

候选审核是唯一允许写入正式知识的入口。实现在 `backend/app/services/knowledge.py::_resolve_review` 与 `backend/app/services/graph.py::promote_candidate`，两者在同一事务内完成。

> 状态前提：本技能以当前工作区的图谱写入切片为前提（`models/graph.py`、`services/graph.py`、迁移 `20261017_0005`、ADR 0007）。如果这些文件不在当前分支，说明该切片尚未提交；先看 `git status`，再决定是补实现还是按规划处理。

## 何时使用

- 修改确认/拒绝、审核事件、候选展示。
- 修改正式节点、关系、证据的写入规则。
- 修改项目图谱、实体/关系详情查询。
- 处理“已确认但未入图”的旧候选。

## 状态机

| 当前 | 动作 | 结果 | 重复相同动作 |
| --- | --- | --- | --- |
| `pending` | `confirm` | `confirmed` + 写正式知识 + 审核事件 | 返回原结果，不重复写入 |
| `pending` | `reject` | `rejected` + 审核事件 | 返回原结果 |
| `confirmed` | `confirm` 且无修改 | 幂等；未入图则补写正式知识，不新增事件 | 幂等 |
| `confirmed` | `reject` 或带不同修改 | HTTP 409 `REVIEW_ALREADY_RESOLVED` | 拒绝 |
| `rejected` | `confirm` | HTTP 409 `REVIEW_ALREADY_RESOLVED` | 拒绝 |

不支持改判、撤销、合并。`changes` 只允许 `name`、`summary`，拒绝时不能带修改。

## 审核流程（锁顺序不能变）

1. 用 `_review_query` 取候选：当前用户、有效项目、来源/任务同项目、任务类型 `knowledge_candidates` 且成功。
2. 对项目行加锁 `SELECT ... FOR UPDATE`，让关系确认与端点确认串行化。
3. `db.refresh(candidate)` 读取锁后的最新状态。
4. 已处理时：相同决策且无不同修改 → 走补写入（仅确认）；否则 409。
5. 关系确认前，查询同任务的两端实体候选，必须都已确认；缺一个返回 409 `REVIEW_ENDPOINTS_UNCONFIRMED`。
6. 用 `UPDATE ... WHERE review_status = 'pending'` 条件更新；`rowcount != 1` → 回滚并返回 409。
7. 写 `review_events`：`action`、`before`、`after`，与候选状态同事务。
8. 确认时调用 `promote_candidate`，仍在同一事务内。
9. 提交后返回 `ReviewRead`（含 `knowledge_id`）。

## 提升规则

- `payload["kind"]` 必须是 `entity` 或 `relation`，否则 409 `KNOWLEDGE_PROMOTION_INVALID`。
- 已存在同 `candidate_id` 的正式记录时直接返回其 ID（幂等）。
- 类型必须在 `EntityType`/`RelationType` 白名单内；名称、摘要去空格后不能为空。
- 重新校验证据：候选所属任务必须是成功的 `knowledge_candidates`；证据 1–5 条；`chunk_id` 属于同一来源/用户/项目；`quote` 逐字存在；行号按原文重算。
- 关系两端必须同任务、同来源、同用户/项目，且 `payload.kind == "entity"`；必要时递归提升已确认端点。
- 正式 ID：实体 `uuid5(candidate_id, "formal-entity-v1")`；关系 `uuid5(candidate_id, "formal-relationship-v1")`；`candidate_id` 唯一约束兜底幂等。
- 证据 ID：`uuid5(formal_id, f"{chunk_id}:{sha256(quote)}")`，同批重复引用去重。
- `valid_from` 取提升时刻，`valid_to = NULL`；历史语义时间和自动 `SUPERSEDES` 状态迁移尚未实现。
- 写入 `knowledge_entities` / `knowledge_relationships` / `knowledge_evidence`，使用 `(id, user_id, project_id)` 组合外键做作用域隔离。

## 图谱读取

`GET /api/v1/projects/{project_id}/graph`：

- 先校验项目属于当前用户且未归档。
- 时间基线 `at = valid_at or now`。
- 可见条件：`status != 'archived'`、`valid_from <= at`、`valid_to IS NULL OR valid_to > at`。
- `center_id` 为空：按 `created_at, id` 取 `limit + 1` 判断截断。
- 有中心节点：中心必须符合当前类型筛选，否则 404；按 `depth`（1–2）双向 BFS，取邻域去重，受 `limit` 限制。
- 边只返回两端都在结果节点集合内的关系，最多 `MAX_EDGES = 500`；任一截断置 `truncated`。
- `evidence_count` 由后端聚合，前端不查询计数。

详情接口：

- `GET /api/v1/knowledge/entities/{entity_id}`：按用户过滤；校验项目有效；按 `valid_at` 判断可见；直接关系最多 100 条（查 101 判断截断）；证据带 `title`、`uri = project://{project_id}/sources/{source_id}`、`quote`、行号、标题路径。
- `GET /api/v1/knowledge/relationships/{relationship_id}`：同样的作用域与时间可见性，返回关系与证据。

## 项目检索

关键词/语义/混合检索：`GET /api/v1/projects/{project_id}/search` 只返回正式实体，沿用图谱 `visible` 与项目校验。关键词搜索名称、摘要和同作用域证据；语义模式只读查询显式构建的 1024 维索引；混合模式按 ADR 0010 以固定权重融合关键词、向量和可见一跳关系，并返回关系解释。修改时追加 `tests/test_search.py`，并同步 ADR 0008/0009/0010 和 API 文档。

## 跨来源演化审核（阶段五）

`services/evolution.py` 管理独立 `knowledge_changes`，不放松抽取关系同来源/同任务端点约束。创建 `SUPERSEDES/SUPPLEMENTS/CONFLICTS_WITH` 建议须有同项目同类型两个有效正式实体、理由、生效时间和可核验正式证据；不调用模型。规范化后相同请求 UUID 幂等。确认时先锁项目，重读建议/端点并重校验证据、有效状态与时间，再由 `graph.apply_reviewed_change` 原子保存审核快照及状态/有效期。它是 `promote_candidate` 之外唯一获准的正式有效期/状态修改边界，不创建无证据语义对象。

替代方向新→旧；旧截止和新起点同为 effective_at。区间半开，不早于双方有效起点、不允许未来、不分叉/合并/环；补充/冲突仅记录分类。历史 API 只遍历已确认替代，最多 100 实体/200 变化，仍校验项目/用户/归档。治理只读最多 1000 当前实体，输出证据缺失、同名重复/可能冲突、孤立建议，不自动写入。测试加入 `tests/test_evolution.py`；原生并发通过 `python -m scripts.verify_native` 的临时 schema 验证，见 ADR 0039。

## 禁止事项

- 不要在 `promote_candidate` 之外创建 `knowledge_entities` / `knowledge_relationships` / `knowledge_evidence`；唯一有效期/状态更新例外是显式人工演化审核的 `apply_reviewed_change`，不能绕过服务或项目锁。
- 不要跳过项目锁和条件更新；否则并发确认会重复审核或重复写入。
- 不要通过 API 暴露 `user_id`、数据库内部 ID 或画布坐标。
- 不要把 `SUPERSEDES` 方向写反：新知识指向旧知识。
- 不要在这一层引入实体合并/消歧；它们仍是后续阶段。
- 不要删除被正式证据引用的分块（`RESTRICT`），否则重新解析会失败。

## 测试配方

必跑：

```bash
cd backend
python -m pytest tests/test_graph.py tests/test_knowledge.py
```

重点用例：

- 确认实体/关系后图谱节点、边、证据数正确，`knowledge_id` 与图谱 ID 一致。
- 重复确认幂等，不新增 `review_events` 和正式记录。
- 关系先于端点确认 → 409；端点被拒绝 → 409。
- 旧“已确认未入图”候选再次确认 → 补写成功且不重复审计。
- 中心节点、一跳/二跳、类型筛选、`limit`、`MAX_EDGES` 截断。
- `valid_at` 早于 `valid_from` → 图谱列表不返回该节点，实体/关系详情返回 404。
- 归档节点从图谱与边中剔除。
- 伪造证据、未知类型、端点跨来源 → 409，事务回滚。

## 完成检查

- [ ] 审核状态、正式记录、证据、审核事件在同一事务提交。
- [ ] 关系确认仍要求两端已确认。
- [ ] 图谱查询仍有用户/项目/时间/数量边界。
- [ ] 双语文档已同步（`KNOWLEDGE_MODEL.md`、`API_CONTRACT.md`、ADR）。
- [ ] 实际运行的测试与结果已记录。
