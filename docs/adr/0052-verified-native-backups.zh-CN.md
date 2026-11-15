# ADR 0052：可验证的原生 PostgreSQL 备份与受控恢复


状态：已接受

日期：2026-10-25

## 决策

使用原生 pg_dump 自定义格式归档，并导出只读可重复读快照。记录归档 SHA-256，以及同快照下所有应用表的行数、规范 JSONB 内容、列、精确类型、约束、索引和扩展指纹。凭据只传入子进程环境；备份使用新目录，不覆盖旧产物。

恢复前校验归档哈希，只创建全新 `ka_restore_*` 数据库，拒绝已有或配置中的数据库。以 `pg_restore --exit-on-error --single-transaction` 恢复并比较指纹。角色、凭据与集群配置不属于此数据库备份。

仅 public 应用 schema 的备份，在角色没有 CREATEDB 时可使用 `restore-schema` 演练。备份保存显式重映射外键的反射 DDL；演练新建 schema，先验证表实际归属及没有指向应用表的外键，再按依赖顺序将 COPY 数据流写入这些表，不对 public 执行数据文件 SQL。全部行、精确类型与结构指纹必须一致。仅规范化 PostgreSQL 冗余 varchar/text 数组 CHECK 输出，保留布尔分组语义。该替代方案不验证创建数据库、角色授权或整个集群恢复。

输入仅为可信本机生成的归档和清单。`--cleanup` 只删除本次调用创建且校验过名称的目标，不删除已有目标。恢复不改变应用配置或自动启用恢复数据。

## 影响

无需新服务/依赖即可复现恢复。已验证本机 18 张表的隔离 schema 恢复，应用数据不变。完整新库恢复需要 CREATEDB 和扩展创建权限，当前应用角色下未验证。见[操作指南](../BACKUP_RESTORE.zh-CN.md)。原生命令选项依据 [pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html) 和 [pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html)。
