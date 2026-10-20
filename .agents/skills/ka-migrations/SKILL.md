---
name: ka-migrations
description: Knowledge Atlas 的 SQLAlchemy 模型与 Alembic 迁移。新增/修改表、列、约束、索引，或排查迁移升级/回滚、SQLite 与 PostgreSQL 差异时使用。触发词：migration, Alembic, schema, model, table, column, 迁移, 模型, 表结构.
---

# 模型与数据库迁移

迁移是正式数据的唯一结构变更入口。实现在 `backend/migrations/versions/`，模型在 `backend/app/models/`，迁移测试在 `backend/tests/test_migrations.py`。

## 何时使用

- 新增表、列、索引、约束或枚举值。
- 修改 `models/domain.py` 或 `models/graph.py`。
- 排查 `alembic upgrade head` 失败、回滚失败、SQLite/PostgreSQL 行为差异。

## 迁移链

| 版本 | 内容 |
| --- | --- |
| `20261017_0001` | 初始领域表（项目、来源、任务、候选）+ PostgreSQL 下创建 pgvector 扩展 |
| `20261017_0002` | `source_chunks` 与行号/位置约束 |
| `20261017_0003` | 任务执行租约、`execution_id`、`attempt_count`（batch alter） |
| `20261017_0004` | `review_events` 审核事件 |
| `20261017_0005` | 正式图谱：实体、关系、证据与作用域外键 |
| `20261018_0006` | 正式实体语义向量：1024 维 pgvector、内容哈希与模型元数据 |
| `20261019_0007` | 来源可选文件夹相对路径 |
| `20261019_0008` | 本地来源仓库身份与来源可空仓库外键 |
| `20261019_0009` | 规范化 GitHub remote 身份与仅远程仓库类型 |
| `20261020_0010` | GitHub provider ID、Commit 快照及逐文件状态 |

当前 head 是 `20261020_0010`。文档里若仍写旧版本，以 `alembic heads` 和迁移目录为准，并顺手修正文档。

## 规则

- **只增不删**：新增列/表优先；删除或重命名列必须有明确理由、数据备份和回滚方案。
- 每个迁移必须有 `upgrade()` 和 `downgrade()`；降级要能回到上一版本。
- 新迁移的 `down_revision` 必须等于当前 head，禁止分叉。
- 非空新列必须给 `server_default` 或先加可空列再回填。
- 约束、索引显式命名，风格与现有迁移一致（`uq_`、`ck_`、`ix_`、`fk_`）。
- PostgreSQL 专属语句（如 `CREATE EXTENSION`）必须判方言，参考 `0001`。
- 需要改 SQLite 测试库能跑的表结构时，用 `op.batch_alter_table`，参考 `0003`。
- 不修改已应用过的迁移；修复用新迁移。
- 迁移只改结构，不调用应用服务、模型方法或网络。

## 新增迁移步骤

1. 从 `backend/` 确认 head：`alembic heads`。
2. 新建 `migrations/versions/<日期>_<序号>_<描述>.py`，例如 `20261017_0006_add_x.py`。
3. 写 `revision`、`down_revision`、`upgrade`、`downgrade`。
4. 同步 `models/`，保持模型与迁移一致（列类型、可空、默认值、索引名）。
5. 加测试：
   - SQLite 临时库 `upgrade` → 断言结构/数据 → `downgrade` → 再 `upgrade`。
   - PostgreSQL 离线编译：`command.upgrade(config, "head", sql=True)`，断言关键 SQL 片段。
6. 本地执行 `alembic upgrade head`，确认 `alembic current` 为新版本。
7. 更新文档中的预期版本与约束说明（双语）。

## 常用命令

```bash
cd backend
alembic heads
alembic current
alembic upgrade head
alembic downgrade -1
alembic upgrade head --sql             # 离线编译，不需要数据库
python -m pytest tests/test_migrations.py
```

## SQLite 与 PostgreSQL 差异

| 行为 | SQLite（测试） | PostgreSQL（真实） |
| --- | --- | --- |
| 行锁 `FOR UPDATE` | 无效果 | 真正串行化 |
| 组合外键 | 可建，默认不强制 | 强制 |
| `CREATE EXTENSION` | 跳过 | 需要权限 |
| 并发/租约竞争 | 测不出 | 必须专项验证 |
| JSON 类型 | 文本存储 | `JSON`（当前未使用 JSONB） |

结论：SQLite 测试证明接口与模型逻辑，不证明 PostgreSQL 锁、并发、扩展和迁移真实执行。涉及并发、租约、去重的改动必须在本机 PostgreSQL 上复验。

## 常见错误

- `Target database is not up to date`：先 `alembic upgrade head` 再生成新迁移。
- 多个 head：检查是否误加分支迁移，合并或修正 `down_revision`。
- SQLite 上报 `ALTER TABLE` 不支持：改用 `batch_alter_table`。
- 非空列没有默认值：旧行插入失败，补 `server_default` 或分两步。
- 模型有索引但迁移没建：用 `alembic check`/对比表结构，保持命名一致。
- 删除被证据引用的分块/来源：外键 `RESTRICT` 会阻止，先处理正式证据。

## 完成检查

- [ ] `python -m pytest tests/test_migrations.py` 通过。
- [ ] `alembic upgrade head` 与 `alembic downgrade -1` 在本机 PostgreSQL 上通过。
- [ ] 升级/降级 SQL 均通过离线编译。
- [ ] 模型、迁移、索引名、约束名一致。
- [ ] 文档中的迁移版本与限制已同步。
- [ ] 破坏性变更已说明回滚与数据影响。
