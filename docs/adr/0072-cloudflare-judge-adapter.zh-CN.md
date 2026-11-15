# ADR 0072：显式 Workers AI 评审适配


- 状态：接受
- 日期：2026-10-30
- 扩展 ADR0070 的供应商选择，匿名模型评审和人工覆盖率0%保持。

## 决策

新增离线供应商选择与原生 Cloudflare REST 适配，显式区分 decision/chat。Clef/Clef-flash 使用 state/questions 和校验后的概率；兼容文本模型使用 messages、JSON Schema，仅生成选项标签。chat 置信度/概率保持 null，引用单元标记不确定。不自动切换模型、格式或供应商。

保留供应商无关输入包和原 Jev CLI/导入路径，新增 scripts.judge_evaluation 与 --allow-judge-calls。Jev 专属标记不能授权 Cloudflare。保持逐次落盘预留、覆盖全部计划的次数上限、零调用预演、新输出目录和失败停止，不重试/续跑。记录模型/模式/协议/配置哈希、实际用量或 null 和 CF 未核验固定权重版本的边界。凭据不进入报告。

## 影响

只覆盖文本评审，不泛化为全部 Workers AI 任务、AI Gateway/外部目录供应商、业务问答/抽取/嵌入切换、页面、迁移或入图修改。响应128 KiB，请求24000 UTF-8 JSON 字节。实现依据官方 API 文档，HTTP 替身不证明真实兼容或质量。holdout/冻结结果/旧调用账本不变，配置字段不授权付费。见[指南](../CLOUDFLARE_EVALUATION.zh-CN.md)。

## 验证

CF/Jev/实验聚焦回归79通过；KA_NATIVE_COMPILERS=1 完整后端862通过、8跳过，应用语句覆盖率95.70%，90%门禁通过。实际 CLI 准备及 CF decision、CF chat、旧 Jev 三次预演各计划54次，预留/完成/评分均0。333个本地 Markdown 目标存在，双语同轮更新，git diff --check 通过。本地 .env 被忽略，冻结输入/结果不变；未改前端/页面/SQL/迁移，因此未重复浏览器、构建和原生数据库验收。真实供应商调用0。
