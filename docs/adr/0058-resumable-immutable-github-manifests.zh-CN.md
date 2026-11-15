# ADR 0058 可续扫的不可变 GitHub 清单


- Status: Accepted
- Date: 2026-10-26

## Decision

扩展 ADR 0018/0019，以 scan_state 保存清单/队列并显式 continue_from_snapshot。固定 commit/tree/ref 且验证用户/项目/仓库。递归截断后按目录 BFS，每步 10 目录、50 份下载/20 MiB，清单最多 250,000 项/深度 64；不改写旧快照。完整序列才对照前一不同提交核对删除，部分扫描不宣称完整删除检测。

## Consequences and alternatives

不采用无界同步扫描；单目录自身截断时明确阻止并提示本地文件夹导入。私有验收仍需真实授权，模拟隔离测试不证明私有连通性。
