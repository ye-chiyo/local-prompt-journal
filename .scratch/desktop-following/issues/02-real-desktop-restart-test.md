Status: ready-for-agent
Execution: resolved

# 实机重启桌面应用，验证采集器跟随停止与恢复

## What to build

提供默认只读预检查、显式运行才重启应用的 PowerShell 脚本。通过当前用户一次性计划任务运行隐藏测试进程，使测试不依赖 Codex 存活。只操作当前安装包路径匹配的桌面进程；不手动启动监视器或采集器，不改变正式库采集策略。

## Acceptance criteria

- 预检查确认应用、监视器、采集来源、监听服务及归属均正常。
- 重启前后核对主进程和采集进程替换、监视器存活、服务端口关闭／恢复。
- 恢复后必须出现更新的采集成功时间，网站 HTTP 200；数据目录和 enabledAt 沿用。
- 外部报告逐步落盘；失败仍尝试重新打开应用，失败不能转为通过。
- 明示本次属于强制结束应用进程后的恢复，不替代正常退出、登录启动或新对话入库验收。

## Comments

2026-10-28：用户要求编写脚本实测重新启动 Codex 后日志服务是否相应重启，已授权本次应用重启。

2026-10-28 16:59（Asia/Shanghai）：脚本语法和默认只读预检查通过。首次独立启动暴露隐藏启动器引号及 MSIX AppData 路径重定向问题；最终采用当前用户隐藏一次性 PowerShell 计划任务，并通过文件句柄取得实际磁盘路径。独立 worker 已写入 RUNNING 报告，等待 90 秒后执行重启。报告：`C:\Users\614\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\LocalPromptJournal\verification\desktop-restart-20261028-165933-c38be316\result.json`。须以该报告最终 PASS／FAIL 为准，目前不能标记实测通过。

## Answer

2026-10-28 17:10:34：首次测试 FAIL 已保留。修正后第二次实机测试全部 PASS；Codex 76344→74292、采集器 64256→74756、监视器 34168 保持存活；应用退出期间原采集器停止、8766 关闭；应用重开后自动恢复，来源可用、新采集成功时间、HTTP 200、原数据库和 enabledAt 均通过。临时测试任务自动移除。报告见 [交验记录](../../../docs/verification/desktop-following.md)。
