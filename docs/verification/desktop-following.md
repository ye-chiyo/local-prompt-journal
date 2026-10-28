# ChatGPT 桌面联动采集验证

日期：2026-10-28（Asia/Shanghai）。范围：[桌面联动规格](../../.scratch/desktop-following/spec.md)、[任务](../../.scratch/desktop-following/issues/01-desktop-following.md)、[ADR 0003](../adr/0003-desktop-following-collector.md)。

## 实现与边界

当前用户计划任务 `LocalPromptJournal ChatGPT Desktop Monitor` 在登录时启动隐藏 pythonw 监视器；安装时也通过任务调度器立即运行，独立于 Codex 进程。旧 Startup 快捷方式已移除。监视器通过当前安装的 AppX 包解析主程序路径，并通过原生命令行查询排除 `--type=` 子进程，孤立辅助进程也不会被当作主程序。每 2 秒检查状态；应用运行时启动采集服务，主进程退出后通过停止文件等待服务清理；应用仍运行而采集进程退出时重新启动。

采集服务显式固定已有正式数据库物理目录 `C:\Users\614\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\LocalPromptJournal\data`。默认目录解析同时检查普通路径和当前 MSIX 包缓存路径：应用内路径可能被重定向，外部终端不会，因此必须统一解析；若发现两个不同数据库则要求显式选择。运行时沿用原 enabledAt 和 dialogue-only 策略，不传 `--start-from-now`。

仅读取本机 Codex App Server 可见的 Codex Local／Worktree 会话。监视器不区分应用当前 UI 模式；采集服务只调用历史读取白名单，不会因此读取普通 ChatGPT 对话。Cloud 会话和未被本机接口暴露的对话不在认证范围内。窗口关闭但桌面主进程仍存活时采集继续。

## 验证

- 13 项桌面行为测试通过，含已有应用、启停／恢复、孤立辅助进程原生检测、MSIX 路径、独立登录任务及卸载幂等。2 项路径回归先失败后通过。
- 完整 `python -X utf8 -m unittest discover -s tests -q`：65 项通过；随后 App Server 隐藏进程标志变更后重跑来源隔离和桌面测试，15 项通过。
- `python -m mypy prompt_journal`：18 个源码文件通过；`git diff --check` 通过。
- 实际安装用户计划任务：目标 `D:\python\pythonw.exe`，参数为仓库 `tools\desktop_monitor.py --data-dir <正式物理路径>`；监视器 PID 34168，父进程来自任务调度器。
- 正式 `/api/status`：running=true、sourceAvailable=true、error=null、3 秒采集周期；`enabledAt=1792940638.277109` 与原值相同。
- 17:10 实机重启结果 PASS：原 Codex PID 76344 退出，原采集 PID 64256 停止，8766 端口关闭；监视器 PID 34168 存活；重新打开 Codex PID 74292 后自动启动采集 PID 74756，新的采集成功时间为 17:10:25，首页 HTTP 200。没有手动启动监视器或采集器。
- 独立测试任务已自动删除，正式监视器任务继续运行。未写入验收对话或删除正式会话。真实 Windows 注销／登录、正常菜单退出、重启后新对话正文入库不在本次实测认证范围内。

## 最终实机报告

2026-10-28 网站入口验收：桌面 `D:\桌面\Codex 日志.lnk` 和当前用户开始菜单“Codex 日志”安装完成；两者通过 Windows Explorer 打开 `http://127.0.0.1:8766/`，不启动终端或依赖 AI。注册桌面目录、快捷方式属性、开始菜单应用列表、重复安装及首页 HTTP 200 已核对；用户确认“目前已经可以打开了”。安装／恢复命令为 `python -m prompt_journal install-shortcuts`。网站仍遵守已确认的 Codex 主进程启停规则。

2026-10-28 17:10:34（Asia/Shanghai）完成：[Markdown 报告](</C:/Users/614/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/LocalPromptJournal/verification/desktop-restart-20261028-170940-b712ff02/result.md>)、[JSON 报告](</C:/Users/614/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/LocalPromptJournal/verification/desktop-restart-20261028-170940-b712ff02/result.json>)。七个检查记录全部 PASS；正式目录和 enabledAt 前后相同。17:11 再次检查 running=true、sourceAvailable=true、error=null、首页 HTTP 200。

## 后续状态复查

首次实机报告（16:59 开始）最终 FAIL：等待全部桌面进程退出超时，不能视为通过。随后发现原监视器不在、网站拒绝连接；修正独立任务启动、正式数据路径、辅助进程识别与测试退出条件后，17:10 的新报告 PASS。两次报告保留各自结果，不覆盖早期失败。

2026-10-28 16:08（Asia/Shanghai）：Startup 快捷方式仍存在，但此前监视器进程已不在，8766 拒绝连接；日志没有正常退出记录，原因尚未确定。重新运行 `install-autostart` 后，16:08:37 监视器启动采集 PID 70224；首页 HTTP 200，状态为 running=true、sourceAvailable=true、error=null，原 `enabledAt` 保持不变。现阶段已验证安装后即时运行；真实 Windows 注销／登录自动启动及监视器本身被外部终止后的可用性不能据此认定已通过。
