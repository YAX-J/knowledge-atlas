# Knowledge Atlas

面向毕业设计的个人技术知识系统：把技术文档、代码和 GitHub 活动整理成可回溯原文的时序知识图谱，并提供带引用的检索与问答。前端 Vue 3，后端 FastAPI，业务数据保存在 PostgreSQL + pgvector。

当前能力、验收边界和后续工作以本页、[当前计划](PLANS.zh-CN.md)、[路线图](docs/ROADMAP.md)及[本轮验收](docs/OPTIMIZATION_20261029.zh-CN.md)为准。此前逐轮检查点已移入[历史文档](docs/archive/pre-optimization-20261029/README.md)，旧实验数字保持不变。

## 当前可用能力

| 环节 | 实现与使用边界 |
| --- | --- |
| 收集资料 | Markdown、多语言代码、文件夹、GitHub 固定提交、Issue/PR/Review/thread 版本；去重、原路径/行号、Worker 租约恢复和有界续扫 |
| 抽取与审核 | 结构化模型候选、精确原文校验、修改/拒绝/具名批量确认；人工确认后事务入图并保存审计 |
| 图谱与治理 | 真实节点/关系、证据定位、历史有效期、替代链和分组演化、别名、合并/解除、撤回/启用、冲突检查 |
| 检索与问答 | 关键词、BM25、来源位置 BM25、向量、混合与 RRF；严格引用、无证据拒答、持久化会话及有界多轮上下文 |
| 代码分析 | 语法结构、静态候选、单轮/只读工具 Agent；显式 Java/TypeScript/Go 编译器声明解析；可选固定提交/本地重复路径版本 |
| 工作台 | 真实业务为默认入口，独立 Mock 演示；URL 恢复项目/来源/知识/历史时间/会话；图谱按关系、检索、身份、演化、停用分区 |
| 验证工具 | 迁移、备份/隔离恢复、原生数据库流程验证、公开实验、盲评工具、千级/万级合成性能测量 |

代码分析始终只读，不运行用户代码、构建脚本或自动写入正式图谱。编译器结果是静态声明身份，不代表完整构建上下文或运行时派发。扫描预算和截断会明确显示。

## 本地启动

先安装 Python、Node.js、原生 PostgreSQL 及 pgvector，并按[环境配置](docs/DEVELOPMENT_SETUP.zh-CN.md)填写后端 `.env`。已有数据先按[备份恢复](docs/BACKUP_RESTORE.zh-CN.md)备份；应用迁移 head 为 `20261026_0018`。就绪检查会拒绝落后、未迁移或缺少关键表/列的数据库。

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,evaluation]"
cd ..\frontend
npm ci
cd ..
.\scripts\start-demo.ps1 -Seed
```

已有虚拟环境时跳过创建步骤。脚本说明、独立 API/Worker 命令及可选 Docker 方案见[演示指南](docs/DEMO.zh-CN.md)。启动和只读状态查询不产生模型费用；抽取、问答、Agent 和索引更新需要显式操作。

## 验收与限制

- 本地应用库已备份、验证隔离恢复并升级至 `0018`，18 张旧业务表内容指纹保持一致；数据库备份只保存在忽略的本地输出目录。
- 本轮使用原生临时 schema 和本地模型替身验证功能；不把替身当真实模型质量。付费公开实验累计账本仍为 84 次模型 /61 次嵌入，本轮没有新增调用。
- [holdout-v3](evaluation/holdout-v3/README.zh-CN.md)包含 7 份固定提交的真实公开技术文档和 24 道新题；与旧开发集隔离，尚未运行付费测试，也没有真实人工评分。用户将稍后填写盲评。
- 私有仓库授权、完整新数据库恢复权限、Docker 和远端 CI 验收仍取决于对应外部环境。这里不将其标记为完成。
- 单用户毕业演示尚无生产认证；团队协作、Webhook 自动同步、IDE 插件与大规模部署不在当前范围。

## 文档与目录

`frontend/` 是工作台；`backend/` 包含 API、Worker、迁移和验证脚本；`evaluation/` 保存冻结语料、结果及性能报告；`docs/` 保存设计和验收。

- [后端与命令](backend/README.zh-CN.md) · [前端结构](docs/FRONTEND.md) · [架构](docs/ARCHITECTURE.md)
- [API 契约](docs/API_CONTRACT.md) · [知识模型](docs/KNOWLEDGE_MODEL.md) · [ADR](docs/adr/README.zh-CN.md)
- [实验说明](evaluation/README.md) · [本轮性能](evaluation/performance/2026-10-29-scale/README.zh-CN.md)
- [当前计划](PLANS.zh-CN.md) · [开发路线](docs/ROADMAP.md) · [变更记录](CHANGELOG.zh-CN.md)
