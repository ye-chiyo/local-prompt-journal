Status: ready-for-agent
Execution: resolved

# 用户直接打开日志网站

## What to build

Windows 桌面和开始菜单各创建“Codex 日志”互联网快捷方式，直接用默认浏览器访问现有 8766 网站，无需 AI 或命令行。安装入口为 `python -m prompt_journal install-shortcuts`，通过独立当前用户任务写入实际 Windows 文件夹，避免 MSIX 重定向导致快捷方式不可见。不改变已经确认的采集及网页服务生命周期。

## Acceptance criteria

- 两个可见入口指向 `http://127.0.0.1:8766/`。
- 重复安装可用，不覆盖同名的无关入口。
- 实际验证文件、网址、网站 HTTP 200，并测试打开入口。
- 明示 Codex 主进程退出后服务停止，此入口不额外启动采集。

## Answer

2026-10-28：已安装桌面 `D:\桌面\Codex 日志.lnk` 和当前用户开始菜单 `Codex 日志.lnk`，使用 Windows Explorer 将网站交给默认浏览器。Windows 注册的桌面目录核对为 `D:\桌面`，快捷方式存在且没有隐藏属性，开始菜单“Codex 日志”已由系统应用列表识别。重复安装通过，网址核对正确，首页 HTTP 200，mypy 18 文件通过。用户先反馈未看到桌面入口，核对后明确确认“目前已经可以打开了”，用户实际打开验证通过。未改变采集与网页生命周期。
