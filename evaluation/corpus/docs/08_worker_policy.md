# Worker 租约策略

记录日期：2026-05-09

解析 Worker 的执行租约为 120 秒，领取任务时必须生成新的 execution_id。

自动执行最多尝试 3 次，旧 execution_id 的完成结果不得覆盖新执行。
