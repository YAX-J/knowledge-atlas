# 原生备份与恢复

2026-10-31 M2：按用户要求将业务库0019→0020→0021升级，每次均先做全新备份及隔离 schema 恢复（先26表、后27表）。保留25再26张原业务表指纹，两个恢复目标已清理，0021就绪 up。私密忽略产物：output/backups/pre-m2-20261031-01 和 pre-m2-0021-20261031-01，详见 [M2 验收](PROJECT_ASSISTANT_M2.zh-CN.md)。schema 演练不等于具备 CREATEDB 的全新库完整恢复。


在 `backend/` 使用既有虚拟环境和本机 PostgreSQL 工具运行。CLI 从后端 `.env` 读取 DATABASE_URL，不打印连接字符串。只使用自己生成并信任的归档和清单，它们包含应用数据与恢复 DDL。备份目录应私密保存且不进入 Git；下列示例使用已忽略的 output。

```powershell
# 必须为新目录，不覆盖以前的备份。
.\.venv\Scripts\python.exe -m scripts.database_backup backup --directory ../output/backups/manual-20261025

# 完整恢复：仅创建新数据库，需要 CREATEDB 和扩展创建权限。
.\.venv\Scripts\python.exe -m scripts.database_backup restore --directory ../output/backups/manual-20261025 --target ka_restore_manual_20261025

# 当前应用角色没有 CREATEDB，可在全新 schema 演练仅含 public 应用表的备份。
.\.venv\Scripts\python.exe -m scripts.database_backup restore-schema --directory ../output/backups/manual-20261025 --target ka_restore_rehearsal_20261025 --cleanup
```

找不到工具时添加 `--bin-dir 'C:/Program Files/PostgreSQL/17/bin'`。默认从 PATH 或 Windows 原生 PostgreSQL 安装中查找。脚本支持不带查询覆盖项的本机 PostgreSQL URL，不授予权限或修改角色。

归档和 manifest.json 使用同一导出一致快照。校验包括文件哈希、每表行数/内容指纹、列、精确类型（含向量维度）、外键/检查/主键约束、索引、扩展和约束验证状态。不备份角色、`.env`、凭据或服务端配置。schema 演练面向当前采用 UUID 的应用表；额外数据库对象应使用完整新库恢复。含非 public 表的备份会被演练入口拒绝，不静默遗漏。

拒绝已有目标和配置中的应用数据库。`--cleanup` 仅删除本次创建的新目标，包括失败时；未指定则可能保留新建的部分目标以供检查。任何恢复都不会切换应用数据库 URL，正式切换须由操作者另行处理。

schema 替代方案恢复保存的 DDL 和数据，写入前验证所有表与外键均在新 schema 内，按依赖顺序流式复制，再比较指纹。成功证明当前服务器内的应用表恢复能力，不等同于新库或整个集群灾难恢复。

本轮最终备份位于 `output/reliability-123-20261025/final-backup-0016/`：18 张表已隔离恢复并校验，目标 schema 随后删除。完成迁移前备份及原生迁移验收后才应用 `20261025_0016`，既有业务数据指纹保留。完整新库恢复尝试因当前角色没有 CREATEDB 被 PostgreSQL 拒绝，未更改任何权限。见[验收记录](RELIABILITY_RETRIEVAL_RECOVERY_20261025.zh-CN.md)。
