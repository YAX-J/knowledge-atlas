# 完整本地演示与 CI

当前实验离线演示见[论文讨论及固定5分钟脚本](HOLDOUT_DISCUSSION_AND_DEMO.zh-CN.md)与[457次裁判报告](../evaluation/results/2026-10-31-holdout-v3-clef-run1/REPORT.zh-CN.md)。展示已保存的直接/跨文档/历史/拒答案例，并展示失败与不确定性；不现场重新付费，也不假定已清理的临时项目存在于应用库。人工评分仍0%。

[English](DEMO.md)

仅用于本机单用户毕业演示，尚无认证，不向公网发布。默认走本机 PostgreSQL + pgvector；Docker 可选。模型和嵌入调用始终需要显式操作，启动不会付费。

## 推荐：原生 Windows

前置：Python 3.13、Node 24、已运行的 PostgreSQL/pgvector，按 [环境文档](DEVELOPMENT_SETUP.zh-CN.md) 配好 `backend/.env`。首次安装：

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,evaluation]"
cd ..\frontend
npm ci
cd ..
.\scripts\start-demo.ps1 -Seed
```

启动器先迁移，再可选建立一个全新的 `[EVAL]` 合成项目，后台启动 API、解析 Worker、前端；访问 `http://127.0.0.1:5174`，API 文档在 `http://127.0.0.1:8001/docs`。后续不需要新项目时去掉 `-Seed`。日志位于 `output/demo-native/<本次运行>/`。端口占用则退出，不终止已有服务；可传 `-ApiPort 8002 -FrontendPort 5175`。保持当前终端，Ctrl+C 仅清理启动器持有的子进程；不删除数据库或演示项目。`-Seed` 每次都新建项目，不是刷新既有项目。

## 可选：Docker Compose

```bash
docker compose up -d --build
# 仅首次显式增加合成项目：
docker compose --profile demo run --rm demo-init
```

访问 `http://localhost:8080`。包含 PostgreSQL/pgvector、API、Worker、前端 nginx 同源代理与健康检查。数据库宿主端口默认 5433，避免占用本机 5432；可设置 `KA_POSTGRES_PORT`、`KA_API_PORT`、`KA_FRONTEND_PORT`。只绑定 loopback。第一次也可用 `docker compose --profile demo up -d --build` 启动全部服务并初始化。

`demo-init` 的 `output/demo/preparation` 已存在时会拒绝重放，避免重复造项目；保留报告并使用原项目。不要为了重试删除业务数据库。普通停止用 `docker compose down`，不加 `-v`，保留命名卷。DeepSeek/嵌入密钥仅由显式环境变量进入 API，不打包进前端。无需密钥即可解析、查看合成审核图谱和关键词检索；语义/问答/Agent 需按各自配置显式调用。初始化后的索引未生成，不伪装成已具备语义能力。

## 答辩演示顺序

1. 资料页选择 `[EVAL]` 项目，查看 Markdown 和代码原文/精确行号。
2. 打开项目图谱，查看正式实体与证据；沿本地证据按钮返回原文。
3. 查看历史替代链，说明合成审核夹具不是模型抽取质量。
4. 源码区可选择单轮或工具 Agent；只有明确接受真实调用费用时执行。普通解析不会调用模型。
5. 展示 [真实实验报告](../evaluation/results/2026-10-24-models/REPORT.zh-CN.md) 与冻结图表，无需现场重新付费。
6. 人工盲评分数仍待真实评审，不以自动检查替代。

## 自动检查

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term
.\.venv\Scripts\python.exe -m scripts.verify_native
cd ..\frontend
npm run test:coverage
npm run build
cd ..
git diff --check
```

`.github/workflows/ci.yml` 在 push/PR/手动触发时运行后端、前端、pgvector 临时 schema 验收和容器构建；不需要模型密钥，不调用供应商。覆盖率报告作为 CI artifact；本地报告在 `output/`。新增组件测试覆盖 API 错误/取消、分析策略与重试、运行锁、问答项目切换、检索条件、人工确认与文本注入边界，不是全站端到端覆盖。

本机已实测原生启动器与 PostgreSQL；Docker 未安装，因此本机未执行镜像构建。CI 配置已加入仓库，不代表 GitHub 上已经运行成功。

具体命令、结果与限制见[交付验收记录](DELIVERY_ACCEPTANCE.zh-CN.md)。
