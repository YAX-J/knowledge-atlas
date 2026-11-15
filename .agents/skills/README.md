# Knowledge Atlas 仓库技能

本目录保存仓库级 Agent Skills。分工是：

- `AGENTS.md` 规定**不可协商的规则**（数据边界、证据优先、提交流程）。
- 本目录的 `SKILL.md` 规定**具体任务怎么做**（步骤、命令、测试配方、常见坑）。

技能与代码冲突时，以代码和 `docs/` 为准，并立即更新对应技能。

## 技能索引

| 技能 | 何时读取 | 覆盖范围 |
| --- | --- | --- |
| [ka-extraction](ka-extraction/SKILL.md) | 改抽取 Schema/提示词、排查抽取失败、真实验收 DeepSeek | `services/deepseek.py`、`services/knowledge.py`、抽取 Schema |
| [ka-review-promotion](ka-review-promotion/SKILL.md) | 确认/拒绝候选、写正式图谱、改图谱查询 | `services/graph.py`、`services/knowledge.py`、图谱 Schema |
| [ka-migrations](ka-migrations/SKILL.md) | 改模型、加表/列、写 Alembic 迁移 | `models/`、`migrations/`、`test_migrations.py` |
| [ka-verify](ka-verify/SKILL.md) | 收尾、跑测试、准备声明“完成” | 避开本机环境陷阱的快速验证流程与仅桌面端浏览器验收 |
| [ka-ingestion](ka-ingestion/SKILL.md) | 改上传、解析、分块、Worker | `services/ingestion.py`、`services/markdown.py`、`services/parsing.py` |
| [ka-frontend-workspace](ka-frontend-workspace/SKILL.md) | 改 Vue 组件、图谱页、交互状态 | `frontend/src/` |
| [ka-docs-sync](ka-docs-sync/SKILL.md) | 改行为、写 ADR、发版、翻译 | `README`、`docs/`、`CHANGELOG`、ADR |

## 使用方式

1. 任务命中某个技能时，先完整读取对应 `SKILL.md`，再开始改代码。
2. 若客户端支持 `.agents/skills/` 自动发现，技能会按 `description` 触发；未自动触发时手动读取。
3. 若客户端只扫描全局技能目录，把本目录复制或链接到 `~/.agents/skills/`，或在 `AGENTS.md` 的“仓库技能”一节按索引查找。
4. 技能中的相对路径均以仓库根目录 `knowledge-atlas/` 为基准。

## 编写规范

- 一个技能只做一件事；`SKILL.md` 控制在 200 行以内。
- frontmatter 的 `description` 必须写清“什么时候用”，同时包含中文场景词和英文关键词。
- 细节较多时拆到 `references/`，主文件只保留流程和索引。
- 不复制 `AGENTS.md` 的规则，只链接；不写真实密钥、私有笔记或完整源码。
- 修改行为、接口、迁移或测试方式时，同步修改对应技能；把这一步纳入“完成定义”。
- 新增技能时更新本索引，并在 `AGENTS.md` 的仓库技能列表中加入一行。
