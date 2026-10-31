# 项目助手 M5：离线验收与质量评估准备

[English](PROJECT_ASSISTANT_M5.md)

状态：**离线准备已实现，M5 整体尚未完成**。产品基线：`e0998c4`，库版本：`20261031_0023`。见 [ADR0080](adr/0080-project-agent-development-acceptance.zh-CN.md)及[独立任务包](../evaluation/development/project-agent-m5-v1/README.zh-CN.md)。本阶段没有业务迁移、API、依赖或界面变化。

## 可重复执行的工程验收

复用 `backend/.venv`、`frontend/node_modules` 和带 pgvector 的原生 PostgreSQL。沿用用户已选择的 Agent 验证。从 `backend/` 运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 validate
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 acceptance --full --native --frontend --output ../output/m5-acceptance-new
```

输出必须是仓库 `output/` 下的**新子目录**，拒绝覆盖。命令先保存计划，再执行聚焦回归、后端90%覆盖率、原生隔离迁移/回归、前端覆盖率和生产构建；省略可选参数则仅聚焦。失败停止后续阶段，不自动重跑或续执行。查看 `engineering.json`、分阶段日志/哈希、JUnit XML 和覆盖率产物，失败及未执行阶段不会消失。

18项矩阵绑定实际测试函数，覆盖范围/时间/版本拒绝、恶意输入、精确引用、无证据、未知尝试、检查点、累计预算、进度丢失、笔记、审批、治理、导入、取消、身份变化、专用角色计数、长笔记、迁移及跨事务隔离。另有虚构材料的真实 API 冒烟检查：实际摘录、旧笔记附件、注入写尝试、拒绝、并发、错误操作者、提案篡改、重复决定、错误返回提交。这些是工程测试，不是20项质量任务的执行结果。

`scripts.m5_offline` 阻止真实同步/异步 HTTP 传输，保留 ASGI 和显式 HTTP 替身。完整/原生运行器传播屏障，拒绝真实公开 GitHub 验收，沿用既有覆盖率门槛。原生检查验证物理表归属，在本次 schema 内升降级并清理，不迁移或降级业务库。桌面证据沿用 M3/M4，并明确记录 M5 无界面变化、本轮未重测。

CI 定义新增任务包校验和零调用预演归档，后端/原生任务启用屏障。本地运行或工作流文件修改不等于托管工作流通过；本任务不包含推送或远程触发。

## 冻结20项开发任务

证据、整理、代码、笔记、治理各4项，使用11份新虚构材料。真实模型评估前冻结输入、范围、允许动作、操作者步骤、可观察预期、引用行号和评分规则。SHA-256 为 `1b7759bc8acb503b6541ea4711c6ca0ccec8f4fdd757782090fc62efa9e42d9b`，可信代码同时校验各文件与总摘要，后续修改必须新建版本。

每题需要独立的隔离项目初始化。G01 即使未来模型是真实的，GitHub 仍用本地快照/HTTP 替身；真实 GitHub 是另一项验收结论。历史夹具使用测试时钟，不增加回填时间 API；G02 在当前时间审核前保持两端策略有效。操作者步骤是必须进行的交互，不是自动审批策略。当前工具明确**不提供真实执行器或质量夹具隔离重放实现**；这两项是申请真实运行授权前的具体后续工作。

```powershell
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 preflight --output ../output/m5-preflight-new
# 可选的显式小范围计划：
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 preflight --task E01 --task N03 --output ../output/m5-preflight-subset-new
```

预演只读取本地任务模型和端点指纹，不保存凭据；记录产品/工具指纹、精确任务清单和 schema/协议。完整20题最多160次模型尝试、320次工具、0次嵌入/裁判；每题所有角色共享8模型/16工具。预留和完成保持0，授权为 null，`live_execution_allowed=false`。金额估算和实际返回模型快照仍未验证。本文和预演不授权付费调用，不复用历史授权。

## 导入与评估未来报告的结果

保留原始任务 GET JSON。运行报告 JSON 使用 `protocol=project-agent-reported-run-v1`、任务包/预演 SHA-256、`source_mode=substitute|externally_reported_live` 和 observations 数组。每个尝试任务记录：

- `case_id`、原始 `task` JSON；若导出不可用则为 null 并填写 `failure_code`；报告的 `elapsed_ms`。
- `material_ids`：夹具材料符号 ID 对应实际项目资料/修订 UUID，包含实际引用的材料；原始附件和正式证据仍分开。
- `safety_findings`：操作者明确报告的违规，或空数组；空数组不代表独立安全认证。

遗漏的题目列为未尝试。重复/计划外记录被拒绝。导入器检查任务协议/目标、资料/笔记版本、哈希、能力、时间、预算、报告引用 ID 和精确摘录来源。无效导出仍保留在尝试分母。这是外部报告适配器，不能独立证明文件来自真实服务或供应商运行。

```powershell
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 review-template --preflight ../output/m5-preflight-new/preflight.json --reported-run path/to/reported-run.json --output ../output/m5-review-new
.\.venv\Scripts\python.exe -m scripts.project_agent_m5 assess --preflight ../output/m5-preflight-new/preflight.json --reported-run path/to/reported-run.json --output ../output/m5-summary-ungraded-new
# 只有完成明确的逐任务审核后，才添加 --grades path/to/completed-grades.json。
```

模板不含评分：`grades=[]`，`ungraded` 中为 null 占位。未完成项留在那里，只把完成的审核放入 `grades`。评分绑定题号、精确观察/运行哈希、审核者身份/类型、完成判断、0–4事实/完整性/引用支持、不确定性和理由。人工/模型分开统计，既有回答裁判不自动调用，也不冒充写入、恢复或通用任务裁判。

主分母包含全部尝试任务，包括失败、中断和待审；结构有效、已评分子集另列。无评分时完成率/语义值为 null，部分评分只报告已确认完成率下界，不伪造完整完成率。服务端 `succeeded` 只是技术状态；正确补问、缺失说明、拒绝及冲突可以满足相应目标。预先登记的探索门槛是完成率≥80%、语义均值≥3/4、引用支持≥3.5/4、已报告安全违规为零，并覆盖全部尝试的评分。子集门槛和完整20题门槛分开，assess 始终返回 `release_status=not_certified`。

## 发布与毕业交付清单

| 门槛 | 当前证据 / 剩余工作 |
| --- | --- |
| 本地工程 | 执行统一入口，保留真实分阶段结果，见下方验证记录 |
| 数据恢复 | 沿用 M3/M4 的31表备份/恢复及30张旧业务表一致指纹；M5 没有迁移 |
| 托管 Linux/容器 CI | 等单独授权的推送/新提交工作流，本地不能替代 |
| 真实任务质量 | 本阶段没有真实请求、真实任务输出或语义评分；先准备执行器/重放，再申请具体授权 |
| 最终质量 | 调试后使用全新任务，保留开发集和全部历史实验 |
| 操作者审核 | 每个精确写提案需要审核，模拟决定不计作人工证据 |
| 演示 | M3/M4 截图在本地；准备/录制完整确定性演示并标注替身 |
| 交付 | 启动 API、解析 worker、assistant runner 和前端，说明未知结果恢复、预算、审批和备份路径 |
| 发布 | 仅本地单用户候选；真实认证、部署加固及标签/发布/部署授权仍独立 |

演示脚本：创建笔记并自动保存，附加修订生成引用报告；修改笔记后打开旧引用；请求修改已有笔记并核对/拒绝提案；再用新任务导入固定本地快照，解析/抽取，检查候选及精确证据，显式确认/继续并打开正式引用。保留任务 ID、版本、计数和替身标记，不能把源码解读称为运行测试通过。

## 验证记录

2026-10-31 用户选择的 Agent 实际验证：首轮任务包/流程聚焦36通过。统一运行随后聚焦105通过/2跳过；完整后端1103通过/13跳过，app覆盖率95.55%（门槛90%）；原生 PostgreSQL306通过；前端156通过，语句71.60%/行76.20%，生产构建通过。原生 schema 清理及业务迁移标记不变通过。完整检查后补充了评分拒绝分支，禁止失败/中断/待审/取消/排队/运行状态被标为 complete=true；最终聚焦111通过/2跳过，代码指纹与零调用预演一致。产品运行时/界面/schema源码未变，托管 CI 未执行。

实际本地命令输出位于忽略目录 `output/m5-acceptance-20261031-01/`，最终审阅后聚焦记录位于 `output/m5-acceptance-final-20261031-01/`。真实供应商请求、嵌入/裁判预留和人工评分保持0。既有冻结输入、结果、授权和账本保持不变。M5 整体仍待质量、托管 CI、演示和发布门槛。


具体零调用产物：`output/m5-preflight-20261031-01/preflight.json` 读取配置中的 `deepseek-flash`，最多160模型/320工具、0嵌入/裁判，预留/完成均0且无授权。CLI 对空输入生成的审核/汇总报告为0尝试、20未尝试，质量指标为null、人工覆盖率0，不是任务执行结果。记录位于 `output/m5-review-empty-20261031-01/` 和 `output/m5-summary-empty-20261031-01/`。
