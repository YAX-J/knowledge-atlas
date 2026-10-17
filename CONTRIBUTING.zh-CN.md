# Knowledge Atlas 贡献与协作规范

[English](CONTRIBUTING.md)

Knowledge Atlas 当前是毕业设计项目，但修改仍应便于审查和复现。

## 开始之前

1. 阅读 [代理规范](AGENTS.zh-CN.md) 和 `docs/` 下的相关文档。
2. 查看 [实施计划](PLANS.zh-CN.md)，确认当前阶段。
3. 每次修改聚焦一个行为或一个文档主题。
4. 实施重要架构变更之前先创建 ADR。

## 本地前端环境

```bash
cd frontend
npm install
npm run dev
```

提交前端修改之前运行：

```bash
npm run build
```

## 本地后端环境

```bash
cd backend
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -e ".[dev]"
python -m pytest
```

数据库结构变更使用 Alembic。不要在应用启动时调用 `Base.metadata.create_all()`；该操作只用于隔离测试。

## 分支与提交约定

建议的分支命名：

- `feat/<short-description>`
- `fix/<short-description>`
- `docs/<short-description>`
- `chore/<short-description>`

提交信息使用简洁、表达动作的摘要。推荐但不强制使用 Conventional Commits 前缀：

```text
feat: add evidence review endpoint
fix: keep timeline selection and detail panel in sync
docs: define temporal relationship direction
```

除非无法分离，否则不要将生成文件、依赖升级、大范围格式调整和功能行为放进同一个提交。

## Pull Request

Pull Request 应说明：

- 改了什么，以及为什么修改。
- 支持哪个用户流程或项目阶段。
- 如何验证。
- 是否修改 API、知识模型、架构或环境配置文档。
- 剩余限制和后续工作。

对于可见界面修改，条件允许时附上当前截图或简短录屏。

## 代码要求

- 优先使用小型、带类型的组件和明确的数据结构。
- Mock 数据与界面组件分离。
- 保持知识模型定义的证据和时序语义。
- 已有测试框架时，新增或更新测试。
- API 处理函数保持简洁，业务持久化流程放在应用服务中。
- 不包含凭据、私有源码或个人数据。

## 文档要求

- 明确区分已完成与规划中的能力。
- 响应结构变化时同步更新 API 示例。
- 长期有效的架构决策记录在 `docs/adr/`。
- 用户可见变化记录在 `CHANGELOG.md` 的 `Unreleased` 小节。

## 审查清单

- [ ] 修改属于当前范围。
- [ ] 相关构建或测试通过。
- [ ] 界面修改已经在合适的视口尺寸下检查。
- [ ] 文档与实现一致。
- [ ] 没有包含生成产物、密钥或无关文件。
- [ ] `git diff --check` 通过。
