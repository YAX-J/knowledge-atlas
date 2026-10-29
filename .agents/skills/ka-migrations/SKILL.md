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
| `20261021_0011` | GitHub Issue/PR 不可变导入版本与来源/任务映射 |
| `20261021_0012` | GitHub PR Review 活动内容摘要版本与来源/任务映射 |
| `20261021_0013` | GitHub PR Review thread 当前状态、解决数量与截断元数据 |
| `20261022_0014` | 已保存 Commit 快照的可空 Markdown 来源/任务外键与来源索引 |

新增 `20261023_0015`：跨来源知识演化建议、作用域端点外键、正式证据引用及不可变审核快照。

新增 `20261025_0016`：每项目最近一次索引更新归属、租约、状态与结果。

当前 head 是 `20261026_0018`。文档里若仍写旧版本，以 `alembic heads` 和迁移目录为准，并顺手修正文档。

原生临时 schema 验收使用 `python -m scripts.verify_native`：Alembic Config 必须设置 `attributes["version_table_schema"]`，`migrations/env.py` 传给在线 context；同时保留 public 以解析 vector。仅设置 `search_path=temp,public` 会回退到业务版本表和业务表，不能作为隔离保证。测试前检查所有核心表确在生成 schema 且初始项目为空；结束只删除自己生成的 schema 并核对业务迁移标记未变。不要对业务 schema 运行验收降级或清理。

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

## Durable rebuild state and native recovery (ADR 0050/0052)

Head 20261025_0016 adds embedding_jobs as one latest project operation, not formal knowledge. Migration upgrade/downgrade must preserve existing business data. Native runner checks physical ownership of all Base metadata tables before tests. For backups use scripts.database_backup with exported snapshot, checksum and structural/content fingerprints; restore only to a fresh validated ka_restore_* database/schema and never alter configured application targets. Schema rehearsal must remap every foreign key and prove none points to public before COPY. CREATEDB/extension privileges are required for full new-database restore; current local role lacks CREATEDB, so do not claim that path passed.

## Audited retirement (ADR 0054)

Head 20261026_0017 adds knowledge_retirements with scoped entity/relationship composite FKs, exclusive owner/category checks and before/after snapshots. Existing business rows must survive migration. Downgrade only removes audit storage and never reopens validity intervals; retain a verified backup before downgrade to preserve audits. Native suite covers retirement races and schema migration; final clean application backup/schema recovery now includes 19 tables. Temporary QA schemas must be cleaned before a public-only schema restore rehearsal; full fresh DB restore remains permission-limited.

## 2026-10-26 功能补全更新

当前 head `20261026_0018`：六张身份/时序/会话表与 repository_snapshots.scan_state。升级加表/可空列；降级删除新增历史/会话，不可用于业务撤销。原生隔离验证必须检查 Base 全表实际位于本任务 schema。

## 2026-10-29 当前优化边界

ADR 0060: readiness validates physically owned version table, exact expected head, six workspace tables and snapshot scan_state. Keep expected-head regression synchronized. Existing app upgrade requires backup and verified isolated recovery; compare old table content using UTC-normalized fingerprints and exclude migration marker/added column. Never auto-upgrade in readiness. Local application is now0018; old0017 status announcements are historical.
