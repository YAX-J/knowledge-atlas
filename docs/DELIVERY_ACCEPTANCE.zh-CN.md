# 毕业补强清单 3—8 验收记录

[English](DELIVERY_ACCEPTANCE.md)

日期：2026-10-24；执行方：沿用用户已选择的 Agent。使用项目虚拟环境，普通测试不调用供应商。

| 检查 | 实际结果 |
| --- | --- |
| 后端全量 `python -m pytest --cov=app --cov-report=term --cov-report=xml:../output/backend-coverage.xml` | 592 通过、5 项按条件跳过，应用语句覆盖 94%；一条既有 Starlette/httpx 弃用警告 |
| 工具/金标/真实验收脚本/图表聚焦测试 | 通过；覆盖非法工具、作用域/参数、伪造目标与轮次预算 |
| 前端 `npm run test:coverage` | 源码/测试严格类型检查及 15 项测试通过；限定客户端/四组件：语句 50%、行 49.82%、分支 47.31%、函数 30% |
| 前端 `npm run build` | Vue 类型检查与生产构建通过 |
| `python -m scripts.verify_native` | 原生 PostgreSQL 17.10 / pgvector 0.8.7 的临时 schema 升级/降级/再升级、集成、竞争/租约及初始化通过；临时 schema 已清理，应用迁移标记不变 |
| `scripts/start-demo.ps1`（不带 `-Seed`） | API 8001 / Worker / Vite 5174 启动并通过就绪检查；Ctrl+C 清理所持进程，专用端口已释放 |
| 系统 Chrome 桌面 1440×1100 | 工具方式选择、Enter 键、真实无候选响应且不调模型；浏览器内模拟加载/失败后重试得到真实空结果；无页面错误/横向溢出，原文区域 axe 审计 0 违规 |
| 5 组科学图表 | 从冻结结果离线生成并逐一目视检查，保留 PNG/SVG、数值与输入 SHA-256 |
| `git diff --check` | 通过 |

本机 Windows 沙箱可能使 TestClient/socket 卡住，因此测试在所需执行权限下运行，没有为此修改业务逻辑。界面失败模拟不是供应商质量验收；真实模型见独立[实验报告](../evaluation/results/2026-10-24-models/REPORT.zh-CN.md)：获准最多 172 次，实际 112 次，仅公开合成输入，本轮无新嵌入。桌面走查未追加模型请求。

覆盖率门禁：后端应用语句至少 90%；前端限定范围语句/行至少 45%、分支 40%、函数 25%。这是初始回归下限，不是完整 UI 覆盖承诺。

本机未验证：Docker 镜像构建（未安装 Docker）、远端 GitHub CI（仅已新增配置）、独立人工盲评、抽取语义质量与代表性/私有仓库模型质量。不新增认证或公网部署。人工分数保持 null/空白，不从自动检查推定。本交付完成开发和已记录的自动验收，不等于人工实验已完成。
