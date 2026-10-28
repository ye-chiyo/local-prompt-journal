Status: ready-for-agent
Execution: resolved

# 随桌面应用启停 Codex 采集

## What to build

依据 [规格](../spec.md) 与 [ADR 0003](../../../docs/adr/0003-desktop-following-collector.md)，实现用户级隐藏登录监视器。监控 ChatGPT 桌面主进程状态，按确认的范围和生命周期启动、停止并恢复本机 Codex 采集服务。

## Acceptance criteria

- [x] 主进程状态改变驱动采集器启动／停止；renderer 子进程不触发采集。
- [x] 监视器启动时应用已运行会立即启动采集器，采集器异常退出会自动重启。
- [x] 应用退出后服务干净停止，沿用原数据目录、`enabledAt` 和保留策略。
- [x] 用户级隐藏登录启动项可幂等安装和移除。
- [x] 公开行为测试（含 renderer 子进程隔离）、类型检查及 Windows 实际进程/启停验证通过。

## Answer

2026-10-28：Windows 用户级 Startup 快捷方式已安装，目标为 `D:\python\pythonw.exe`，参数为仓库的 `tools\desktop_monitor.py`。首次复验发现快捷方式已不在 Startup 文件夹；重新执行安装命令后监视器 PID 60132 成功启动采集 PID 77976。`/api/status` 为 running/sourceAvailable、error=null，`enabledAt=1792940638.277109` 未变。发现并修复日志函数递归错误；同时修正专项测试夹具。61 项完整回归、9 项桌面联动测试、mypy 18 个源码文件及 `git diff --check` 通过。进程检查未发现监视器创建的 PowerShell 查询进程。卸载测试覆盖幂等及停止运行监视器；真实用户快捷方式保留。

## Comments

2026-10-28：用户确认随 ChatGPT 桌面应用启动；只采集 Codex Local／Worktree；登录后隐藏监视器待机；安装时若应用已运行立即启动；主进程退出后停止；采集异常时自动恢复。测试边界经用户确认，已完成实现和实机验证。

2026-10-28 17:10：上述早期 Startup 实现已由独立的当前用户登录计划任务取代；修复 MSIX 数据目录差异和孤立辅助进程识别后完成真实重启 PASS。当前实现和报告以 [最新交验记录](../../../docs/verification/desktop-following.md) 为准。
