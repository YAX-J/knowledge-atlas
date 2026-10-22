# ADR 0032：检索有界 Java 源码符号并打开原文分块

[English](0032-bounded-code-symbol-search.md)

- 状态：已接受
- 日期：2026-10-22

## 决策

- 增加只读 `GET /projects/{project_id}/code-symbols`，只检索 ready Java 来源。必填名称/路径字面查询不区分大小写，可按仓库及符号类型筛选，返回 1–100 条（默认 50）。保留用户/项目/仓库访问校验及不可变来源版本。
- 与单文件大纲共享同一声明/符号生成函数，不重复分析调用关系、不建立第二套持久化索引。按较早创建优先，最多扫描 100 份来源、20 MiB 原文，每份最多 200 符号。精确名称优先于限定名及仅路径匹配，再按路径/行号/类型/UUID 稳定排序。
- 返回原符号/来源/仓库/任务身份、行号、可空分块 ID/0 起始位置及既有固定 Commit/行号 GitHub URL。`scanned_source_count` 与 `matched_count` 只描述有界扫描；`truncated` 覆盖所有扫描/输出省略。这不是编译器全局索引或已审核代码知识。
- 资料工作台新增表单与可滚动结果列表。App 请求序号使条件修改、清空、项目及导航变化前的请求失效。打开命中先载来源，再读取正确分块页（既有默认 20 条），聚焦并高亮原文；缺少任务映射的旧 ready 来源仍可读取。
- 保留既有前端约定、数据库结构、知识审核边界与不调用模型的行为。不增加编译器、数据库迁移、路由/状态库、全局语义索引、来源修改或正式实体类型。

## 验证

沿用用户已选择的 Agent 执行方，使用既有后端虚拟环境与前端依赖：

```powershell
# backend/
.\.venv\Scripts\python.exe -m pytest tests/test_code_search.py tests/test_java_v1.py tests/test_java_structure.py tests/test_java_static_imports.py tests/test_parsing.py
.\.venv\Scripts\python.exe -m pytest
# frontend/
npm run build
# repository root
git diff --check
```

桌面浏览器使用真实 API、本机 PostgreSQL 的任务专用临时 schema、8001/5174 端口及公开夹具。覆盖筛选、原文/分页/焦点、长路径、滚动、空/重试/清空状态与项目切换时迟到响应。故障/延迟只在临时验收脚本中注入，不代表真实 GitHub/LLM 验收。

2026-10-22 Agent 执行结果：149 项聚焦与 316 项完整后端测试通过，含 22 项新增搜索用例，保留既有 Starlette 弃用警告。前端构建通过。本机 PostgreSQL 桌面走查通过，包括跳转 method64 至第 4/4 页第 66 行、长路径、50 条上限、筛选、空结果、重试、清空/焦点及切项目响应隔离。新增搜索区域 axe-core 检查零违规、零待人工确认。未执行迁移、真实 GitHub 或模型调用。

最终桌面复验还确认：进入证据问答再返回资料页，表单/结果均清空。两个任务专用 PostgreSQL schema 已移除，独立浏览器/API/前端会话已关闭；现有 8000/5173 服务保留。

## 限制

只能命中当前支持的 Java 声明。较早不可变版本保留独立结果。前 100 份有效来源不代表完整仓库覆盖；收窄仓库/关键词也不保证找到被省略的后续文件。UI 仓库选项来自已加载的仓库列表页。阶段四仍在进行中。
