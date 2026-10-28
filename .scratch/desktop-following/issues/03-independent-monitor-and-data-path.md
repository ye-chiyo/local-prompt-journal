Status: ready-for-agent
Execution: resolved

# 修复桌面监视器独立运行与外部终端数据路径

## Problem

用户在外部 PowerShell 执行重启测试时报 monitor not running，8766 网站也不可用。原监视器进程确已不存在；旧实机测试报告为 FAIL（等待全部桌面进程退出超时）。外部终端还会通过未重定向 AppData 访问另一数据目录。

## Changes

- 当前用户计划任务登录触发并立即启动 pythonw 监视器，运行独立于 Codex；沿用原任务名称，移除旧 Startup 快捷方式。
- 显式固定已有正式数据库物理路径；外部 CLI 与测试自动发现已有 MSIX 数据库，不静默创建另一库；存在多个独立库时要求明确选择。
- 生产进程识别读取真实命令行排除 orphan renderer/utility；测试以主进程退出为准，终止失败必须报告。
- CLI monitor 接受显式数据目录，过期 PID 不再阻碍重装。

## Verification

- 原预检查命令已复现相同失败，修复后通过。
- 2 项路径回归先失败后通过；13 项桌面行为测试通过，其中真实 Windows 进程测试覆盖主程序与孤立辅助进程。
- 65 项完整回归、mypy 18 文件通过。独立任务父进程与桌面主进程不同。
- 首页 HTTP 200、来源可用、error=null，原 enabledAt 保持不变。实机重启复测仍待最终报告。

## Answer

2026-10-28 17:10：实机重启复测 PASS，原监视器在 Codex 退出后持续存活，并在 Codex 重开后启动新采集进程。17:11 网站 HTTP 200、采集来源可用、无错误。原报错的预检查命令已通过；详细报告见 [交验记录](../../../docs/verification/desktop-following.md)。真实注销／登录尚未实施，不计入本次通过范围。
