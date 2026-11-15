# ADR 0035：从证据跳转到精确原文分块


- 状态：已接受
- 日期：2026-10-22

## 决策

- 新增只读 `GET /projects/{project_id}/sources/{source_id}/chunks/{chunk_id}`，返回既有分块形状，包括从 0 开始的位置、精确内容、UUID、哈希和包含式行号。校验未归档项目及来源/分块连接后的用户/项目/来源作用域。缺失或错配返回 404 `SOURCE_CHUNK_NOT_FOUND`，项目不可访问沿用项目 404；不要求解析任务仍存活。
- 使用正式图谱详情、知识搜索证据和回答引用中已有的来源/分块 UUID；按钮只发出 `EvidenceLocator` 意图，App 编排进入资料工作台、初始页 `floor(position / 20) + 1`、原分块焦点和既有高亮。不按文件名猜目标、不解析 `project://` 字符串、不近似搜索引用，也不扫描所有分块页。
- 独立维护加载/错误/重试/取消及请求序号；切项目/资料、取消或离开资料页使旧定位和详情请求失效。精确分块加载且可展示后才报告成功，缺失/不可用不回退其他来源或 Mock；新定位清除旧成功提示。
- 复用既有资料解析/审核与 GitHub 外链，不启动任务/模型/供应商请求。本地分块导航不改变证据文字、正式知识、时序语义或数据库结构；head 仍是 `20261022_0014`，阶段四继续进行。

## 验证

用户此前已选择 Agent 执行。前提：已有后端虚拟环境、前端依赖和本机 PostgreSQL/pgvector。命令：

```powershell
# backend/
.\.venv\Scripts\python.exe -m pytest tests/test_chunk_lookup.py tests/test_parsing.py tests/test_graph.py tests/test_questions.py
.\.venv\Scripts\python.exe -m pytest
# frontend/
npm run build
# 仓库根目录
git diff --check
```

2026-10-22 实际结果：32 项聚焦测试、371 项完整后端测试通过（新增 13 个分块定位用例），前端类型检查/构建通过；保留既有 Starlette/httpx 弃用警告。覆盖 Markdown/Java 精确字节、无任务的第 4 页定位、只读分块计数、来源/分块/用户/项目错配、归档项目及缺失/未解析分块。

本机 PostgreSQL 验收使用任务临时 schema 和 65 段合成原文；精确查询定位到 position 64、第 129 行，图谱与关键词证据均打开第 4/4 页并聚焦/高亮原 UUID。临时脚本注入一次短暂错误用于重试。浏览器回答明确使用模拟内容，只证明引用导航，不证明真实模型质量。

桌面亦通过模拟回答引用的键盘原文跳转、取消与切项目迟到响应隔离、精确原文及无横向溢出。回答证据区 axe-core 零违规/待确认；就绪检查 PostgreSQL 为 `up`。验收后任务专属 schema/脚本已删除，专用浏览器/API/Vite 会话已关闭；保留既有 8000/5173 服务和业务数据，未请求真实 GitHub/模型。
