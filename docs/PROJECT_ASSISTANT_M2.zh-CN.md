# 项目助手 M2


M2 按 [ADR0077](adr/0077-durable-assistant-execution.zh-CN.md)实现并通过本地验证；业务库/源码 head 均为 `20261031_0021`。M3–M5 仍为规划，本轮零真实调用，真实任务质量未测量。

## 运行和继续任务

界面默认提交 assistant-task-v2，返回202/queued，不调用模型。在 backend 复用既有虚拟环境启动独立消费者：

```powershell
.\.venv\Scripts\python.exe -m app.assistant_runner
# 最多处理一项排队任务后退出：
.\.venv\Scripts\python.exe -m app.assistant_runner --once
```

原生演示启动器及可选 Compose 均将 runner 与解析 Worker 分开启动。仅显式新提交的 async_v2 任务可被消费。v1 仍同步200；旧 AgentRun 和解析任务不消费。只有用户提交可执行新任务后才使用已配置供应商，本次实现/验证不授权新供应商实验。

每次认领生成唯一执行令牌和300秒租约；模型/工具传输前持久化预留。每项模型决策或单个工具结果校验后，尝试回执、循环状态及后端引用池原子提交。继续时跳过已完成步骤，包括部分工具批次内已完成的工具；最终决策已保存时可在重启后零新增模型发布产物。报告和产物受同一执行归属保护原子保存。

失败/过期任务不自动重新排队。显式继续将唯一请求 UUID 绑定到精确任务修订/检查点；未知模型结果须确认，仍保留计数，后续新尝试可能计费。重复继续 UUID 仅读取回执，不能增加范围/预算。模型/角色/工具次数累计；时间为边界保存的已测量活跃时间，未知传输时长和停机等待不承诺精确累计墙钟度量。取消阻止后续步骤/发布，在途请求仍可能完成并计数；过期/旧执行者不能发布。补问保留 ask_user 保存结果，需要补充目标后新建任务，input/审批/写入接口仍未实现。

新增 assistant_attempts、assistant_steps、assistant_artifacts、assistant_continuations。业务检查点保存有范围的用户/工具正文；运维事件及尝试元数据不含提示词/工具正文。记录随项目保留，无自动 TTL/裁剪；归档后不可见，物理删除项目时级联删除所属记录，不新增删除接口。检查点最多16份、每份200000 JSON字符，并沿用既有角色/来源/输入/输出/引用预算。提交固定知识时间及来源版本；执行前发现运行时/模型/端点/工具契约或来源哈希漂移即停止，不发起模型尝试。

## 实际验证，2026-10-31

| 检查 | 结果 |
| --- | --- |
| 初始兼容 | 后端61、前端26通过 |
| 扩展后端聚焦 |87通过、1项仅原生测试跳过 |
| 完整后端覆盖率 |1036通过、12跳过，95.42%，沿用90%门槛 |
| 原生 PostgreSQL17.10 / pgvector0.8.7 |274通过，包含双消费者行锁竞争；隔离升/降/升级，自有 schema 清理 |
| 前端覆盖率/构建 |143通过；行75.60%、语句71.20%、分支64.26%、函数55.30%，既有门槛/构建通过 |
| 最终聚焦 | OpenAPI 断言后后端16通过/1项仅原生跳过；文案/布局调整后前端29及构建通过 |
| 启动配置 | PowerShell 启动器 AST、Compose YAML/API-runner 供应商字段一致性通过；本机没有 Docker，容器启动/远端 CI 未验证 |
| 交付检查 | 工作区/暂存差异空白检查及 Markdown 本地链接通过；暂存审查排除实验/数据/备份/生成物/依赖/环境文件和凭据模式匹配 |
| 桌面 Chrome1440x1000 | 排队/重载零调用、后台执行、未知结果确认、继续/回执重放、在途取消、精确范围/引用、键盘 Space/Tab/Enter、空项目、项目 fencing 和面板滚动通过；无页面错误或横向溢出 |

桌面 API 使用自有原生 schema，通过独立线程/数据库会话运行同一 runner 服务；模型为本地函数替身，外部 HTTP 被阻止。实际 runner CLI 在空业务队列上也成功退出。首份报告使用2模型/3工具，含四个 source/code/knowledge 引用。第二次模型失败后继续，任务累计3模型、工具保持3；重复继续回执后全局替身计数仍为5。在途取消保留1次尝试、无结果/产物，迟到结果不能写回（计数6）。另一恢复任务用 Space/Tab/Enter 完成确认/继续（计数9），空项目提交后仍为9。界面展示有效剩余协调预算。浏览器/API/runner/Vite 及临时 schema 已清理。这些是本地工程结果，不是远端 Linux/容器 CI 或真实模型质量。

backend 实际运行聚焦 `pytest tests/test_assistant_execution.py tests/test_migrations.py tests/test_project_assistant.py tests/test_multi_agent.py tests/test_agent_progress.py tests/test_agent_tools.py tests/test_health.py`、一次完整 `pytest --cov=app --cov-fail-under=90 --cov-report=term-missing --cov-report=xml:../output/m2-backend-coverage.xml` 及 `python -m scripts.verify_native`。全新 --basetemp 为 `../output/m2-focused-20261031-r2`、`../output/m2-full-20261031-r1`、`../output/m2-final-focused-20261031-r1`。前端运行 npm run test:coverage、受影响测试和 npm run build。沿用用户选择的 Agent 执行方，复用既有依赖，在已知 Windows 沙箱限制之外执行 TestClient/Vite。

## 业务迁移依据

0019→0020 前完成26表备份及隔离恢复，保留25张原业务表指纹；随后对0020再做27表全新备份/恢复，才升级0021，保留26张原业务表指纹。两个恢复 schema 均删除；真实就绪接口200，数据库/schema均 up。私密忽略备份位于 `output/backups/pre-m2-20261031-01/` 和 `output/backups/pre-m2-0021-20261031-01/`，脱敏迁移 JSON 与 manifest 同目录。浏览器产物为 `output/m2-browser-20261031/` 本地忽略文件；备份/数据/环境文件不提交。冻结实验/账本和人工0%保持。
