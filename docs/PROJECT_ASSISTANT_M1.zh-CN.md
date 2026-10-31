# 项目助手 M1

历史 M1 验收记录。当前 M2 执行与业务迁移见 [PROJECT_ASSISTANT_M2](PROJECT_ASSISTANT_M2.zh-CN.md)；下方 M1 未升级/无 runner 的陈述描述该历史轮次。

[English](PROJECT_ASSISTANT_M1.md)

已通过本地供应商替身验证，见 [ADR 0076](adr/0076-read-only-project-assistant.zh-CN.md)。源码迁移 head 为 `20261031_0020`，尚未升级已安装业务数据库。

在 Agent 工作区选择项目、输入目标，可跨资料分页勾选最多 20 份已解析文档/代码版本。不附资料时只检索项目正式知识。代码精确使用所选本地 UUID，或选择包含全部所选代码版本的已保存提交。提交后核对保存范围、计数、工具事件、类型化报告和精确引用。原始/源码片段和正式证据保持区分；附有引用不自动证明语义正确。有分块时引用跳到精确分块，否则打开精确来源 UUID。补问需要补充目标后新建任务。

任务同步执行；历史、轮询、刷新及按项目 sessionStorage 恢复均只用 GET。提交结果未知时先读取 UUID，再显式重发同 UUID；重放不会重新执行。过期任务显示中断；新尝试需要单独提交新 UUID。即使本地任务失败，远端传输结果仍可能未知。M1 没有 runner、取消、继续、笔记编辑、导入或受治理写入。不授权真实模型实验；冻结数据/账本和人工覆盖率 0% 保持。

## 本地验证（2026-10-31）

| 检查 | 实际结果 |
| --- | --- |
| 后端/迁移/旧流程进度聚焦 | 61 通过；全新 `output/m1-focused-20261031-r2` |
| 完整后端覆盖率 | 1019 通过、11 跳过；95.44%，沿用 90% 门槛；`output/m1-full-20261031-r1` |
| PostgreSQL 17.10 / pgvector 0.8.7 | 隔离升/降/升级及 257 项通过；临时 schema 删除，业务版本标记不变 |
| 前端覆盖率/类型检查 | 140 通过；行75.30%、语句71%、分支63.89%、函数54.97%，既有门槛通过 |
| 最终前端聚焦/生产构建 | 刷新按钮对齐调整后 26 项通过，构建通过 |
| 交付检查 | 工作区/暂存 `git diff --check` 和变更 Markdown 本地链接通过；暂存排除实验、生成物、依赖、环境文件和凭据模式匹配 |
| 桌面系统 Chrome，1440x1000 | 资料分页/选择、固定提交、类型化报告、精确分块导航/焦点、补问、失败、空态、刷新/重载、未知响应 GET 恢复通过；无页面错误或横向溢出 |

浏览器报告结合两份所选版本与正式知识，共四个 source/code/knowledge 引用，保留合成固定提交，使用 2 模型 / 3 工具 / 0 嵌入。刷新/重载后替身计数仍为2；补问/失败各增加1。故意丢弃一次成功响应后计数为6，GET 恢复清除待确认状态且计数不增；空项目提交后仍为6。六次均为本地函数替身，外部 HTTP 传输被阻止。780px 报告面板可滚动查看1448px 展开的报告/事件，键盘焦点可见；最终刷新按钮高36px。隔离 API 数据库/schema 就绪均 up，未升级业务库。

Windows 沙箱最初无法执行 TestClient / Vite 临时文件重命名，授权后使用既有环境在沙箱外重跑。临时 QA 脚本需要 Alembic URL 转义修正，失败初始化先清理自有 schema 再重试。验收后清理浏览器/API/Vite 会话；本地忽略的产物位于 `output/m1-browser-20261031/`，覆盖率 XML 位于 `output/m1-backend-coverage.xml`。这些结果不代表真实模型任务质量、人工评分或远端 Linux/容器 CI；M2–M5 仍为规划。

用户已选择 Agent 执行，记录的结果均由本轮实际运行得到，供应商为本地替身。前提：复用 `.venv` / node_modules；本机 PostgreSQL 的 public 已安装 pgvector，并有创建临时隔离 schema 权限。模型使用本地替身，无需新依赖或真实调用。每轮使用 output 下全新、被忽略的临时目录。

```powershell
# backend
.\.venv\Scripts\python.exe -m pytest tests/test_project_assistant.py tests/test_migrations.py tests/test_multi_agent.py tests/test_agent_progress.py --basetemp ../output/m1-focused-temp
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-fail-under=90 --cov-report=term-missing --basetemp ../output/m1-full-temp
.\.venv\Scripts\python.exe -m scripts.verify_native
# frontend
npm run test:coverage
npm run build
# 仓库根目录
git diff --check
```

预期：聚焦/完整回归通过，覆盖率 >=90%，前端检查/构建通过；原生隔离升/降/升级和范围/租约检查通过，业务库迁移标记不变。暂存检查排除生成物、依赖和密钥。桌面浏览器覆盖资料分页/选择、固定快照、空/缺失信息/补问/失败、精确引用、未知提交恢复、刷新零 POST、项目 fencing、键盘焦点、长文本和面板滚动，使用本地模型替身。这些检查不测量真实模型质量。业务库升级另按备份/恢复流程执行。
