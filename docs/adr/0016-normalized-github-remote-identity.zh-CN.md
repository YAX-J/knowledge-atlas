# ADR 0016 在仓库导入前规范化 GitHub remote 身份


- 状态：Accepted
- 日期：2026-10-19

## 背景

本地文件夹名称可以提供仓库边界，但不能跨设备标识同一仓库，也不足以支撑后续 GitHub 导入。如果在远程身份规则明确前导入内容，同一代码库的本地文件夹和 GitHub 来源可能被创建成两条仓库记录。直接保存任意 clone 字符串还可能保留凭据，或把 HTTPS 与 SSH 形式误认为不同仓库。

## 决策

- 为 `source_repositories` 增加可空的 `provider`、`remote_owner`、`remote_name` 和规范化 `remote_url`。既有本地仓库四个字段均为空时仍然有效。
- 首个支持的 provider 为 `github`，仅远程登记的仓库类型为 `git_remote`。
- 通过 `POST /projects/{project_id}/repositories/resolve-github` 解析身份。接受 GitHub HTTPS、SCP 风格 SSH 与 `ssh://` remote；拒绝其他主机、查询参数、片段和 HTTPS 中携带凭据的地址。
- owner 与仓库名称统一转为小写，并保存 `https://github.com/{owner}/{repository}` 作为规范 URL。身份按当前用户、项目、provider、owner 和仓库名唯一。
- 可以把该身份关联到一条尚未关联 remote 的 `local_folder` 仓库；未提供本地仓库 ID 时，创建或复用仅远程仓库记录。
- 复用项目行锁串行化解析。本切片不访问 GitHub、不验证仓库是否存在、不请求凭据、不克隆文件，也不推断默认分支。

## 影响

项目现在拥有可被后续 GitHub 来源导入复用的仓库 UUID，也支持先显式关联本地文件夹。等价的 HTTPS 与 SSH 地址会幂等解析；关联冲突返回明确的 HTTP 409，而不会静默合并仓库记录。

该身份仍弱于 GitHub 平台仓库 ID：仓库改名和所有权转移无法自动识别，当前以小写 owner/name 坐标为键。远程登记也不能证明仓库真实存在或当前可访问。分支、Commit、文件读取、删除对账、Webhook 和令牌仍属于后续能力。

将迁移 `20261019_0009` 降级到 `0008` 时，会移除本地仓库已关联的 remote 元数据，并删除旧结构无法表示的仅远程 `git_remote` 记录；不会删除本地仓库或其资料。

## 评估过的替代方案

- 原样保存用户提交的 remote：拒绝，因为等价的 HTTPS/SSH 地址会分裂，并可能持久化含凭据的 URL。
- 立即调用 GitHub 并使用平台仓库 ID：推迟到实现公开或鉴权 GitHub 导入时处理。
- 自动合并既有本地仓库与仅远程仓库：拒绝，因为移动资料会改变去重和跨文件解析边界。
