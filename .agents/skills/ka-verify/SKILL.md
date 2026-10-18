---
name: ka-verify
description: Knowledge Atlas 的收尾验证与“完成”判定。准备声称任务完成、提交前、修改后端/前端/文档后使用。触发词：verify, test, build, check, done, 验证, 测试, 构建, 收尾.
---

# 收尾验证

本技能只做一件事：在说“完成”之前，按改动范围跑够检查，并如实报告。仓库目前没有 CI，这一步不能省。

## 何时使用

- 任何代码、迁移、文档改动之后。
- 准备提交或回复“已完成”之前。
- 排查“本地能过、真实服务不过”的差异。

## 黄金规则

- 只报告**实际运行过**的命令和结果；没跑的检查明确写“未运行 + 原因”。
- SQLite 测试通过 ≠ PostgreSQL 验收通过。
- `npm run build` 通过 ≠ 浏览器交互正确。
- 不把 Mock 响应说成真实模型质量。
- 不把“文档已写”说成“功能已实现”。

## 快速命令

```bash
# 仓库根目录
git diff --check
git status --short

# 后端
cd backend && python -m pytest

# 前端
cd ../frontend && npm run build
```

按改动追加：

| 改动 | 追加检查 |
| --- | --- |
| 抽取/审核/图谱 | `python -m pytest tests/test_knowledge.py tests/test_graph.py` |
| 关键词检索 | `python -m pytest tests/test_search.py`；原生 PostgreSQL 验证排序、证据、多词、通配符；浏览器检查清空、重试、类型、详情和迟到响应 |
| 语义检索 | `python -m pytest tests/test_search.py tests/test_migrations.py`；原生 PostgreSQL 验证 1024 维写入和余弦排序；真实嵌入服务验收必须单独注明 |
| 混合检索 | `python -m pytest tests/test_search.py tests/test_graph.py`；验证归一化组成得分、关系归档/时间过滤、稳定排序；真实 PostgreSQL 与嵌入服务验收单独注明 |
| 证据问答 | `python -m pytest tests/test_questions.py tests/test_search.py`；验证无证据不调用模型、严格引用归属、错误映射、切换项目迟到响应；真实 DeepSeek 质量单独注明 |
| 导入/解析/Worker | `python -m pytest tests/test_sources.py tests/test_parsing.py tests/test_worker.py` |
| 迁移/模型 | `python -m pytest tests/test_migrations.py` + `alembic upgrade head` |
| 前端可见界面 | 浏览器桌面 + 手机宽度走查 |
| 文档 | 双语链接、命令、状态标注 |

## 后端清单

- [ ] `python -m pytest` 全绿，或明确列出失败用例与原因。
- [ ] 新行为有聚焦测试，不只靠手工验证。
- [ ] 迁移可升降级，离线 SQL 可编译。
- [ ] 真实 PostgreSQL：`alembic upgrade head` 成功，`GET /api/v1/health/ready` 返回 `up`。
- [ ] Worker 改动：`python -m app.worker --once` 冒烟，退出码符合预期。
- [ ] 没有把密钥、完整原文、模型响应写进日志或测试。
- [ ] 错误仍走统一 `error` 结构，未新增未处理的 500。

## 前端清单

- [ ] `npm run build` 通过（含 `vue-tsc`）。
- [ ] 桌面与手机宽度下：无横向溢出、面板可滚动、长文件名/长知识名不撑破布局。
- [ ] 加载、空数据、错误、重试四种状态都能到达且有反馈。
- [ ] 键盘可完成主要操作，焦点可见；`prefers-reduced-motion` 下动效收敛。
- [ ] 原文只做文本插值，没有 `v-html`。
- [ ] 真实接口失败时展示错误，不回退成假数据。
- [ ] 图谱页：节点/关系可选，详情证据可读，筛选/深度/返回总览可用。
- [ ] 问答页：支持/不足/错误状态可达，引用可跳实体，切换项目不保留旧回答，手机宽度可滚动。

## 真实服务验收（涉及导入/抽取/图谱时）

1. 启动本机 PostgreSQL（含 pgvector），确认 `backend/.env` 的 `DATABASE_URL`。
2. `alembic upgrade head`，启动 `uvicorn app.main:app --reload`。
3. 另开终端 `python -m app.worker`（或按需 `--once`）。
4. 创建项目 → 上传 Markdown → 解析 → 查看分块行号。
5. 重复上传相同字节，确认复用来源/任务。
6. 抽取候选（真实 key 或模拟响应，注明是哪种）→ 确认实体 → 确认关系 → 查看项目图谱与证据。
7. 重启 API，确认数据仍在。
8. 记录哪些步骤通过、哪些仍是已知限制。

## 文档清单

- [ ] 改 API 形状 → `docs/API_CONTRACT.md`。
- [ ] 改知识模型 → `docs/KNOWLEDGE_MODEL.md`。
- [ ] 改架构决策 → 新 ADR。
- [ ] 改能力/安装/结构 → `README.md`。
- [ ] 变更记录进 `CHANGELOG.md` 的 `Unreleased`。
- [ ] 有 `.zh-CN.md` 的文档成对更新，语言链接有效。
- [ ] 计划中的能力仍明确标注“规划中”。

## 提交前

- [ ] 只暂存本轮相关文件，保留无关的用户改动。
- [ ] `git diff --cached` 逐块看过，没有调试代码、生成物、`.env`。
- [ ] 提交信息描述最终行为，而不是“update files”。
- [ ] 提交后报告哈希与仍未提交的改动。
- [ ] 无法提交时保留工作并说明原因，不谎报成功。

## 报告模板

```text
已运行：
- cd backend && python -m pytest  → 全部通过
- cd frontend && npm run build    → 通过
- git diff --check                → 无输出

未运行：
- 真实 PostgreSQL 验收（本机服务未启动）
- 真实 DeepSeek 调用（未配置密钥）

结论：
- 后端逻辑与前端构建已验证；真实服务与模型质量仍待验收。
```

## 环境说明

- 默认验收路径是用户本机原生 PostgreSQL 17 + pgvector；Docker Compose 可选，不是前提。
- 后端测试用内存 SQLite，不验证行锁、组合外键强制、扩展和并发。
- 若 shell / 构建环境不可用（例如沙箱文件权限问题），直接说明“无法运行”，不要用静态阅读冒充验证结果。
