# 在插件详情页提供本机日志网站入口

Status: ready-for-human

Execution: completed

阶段：实现与宿主验收完成

## 范围

在“本机会话记录”插件详情页提供指向 `http://127.0.0.1:8766/` 的网站入口。入口只打开默认浏览器中的既有网页，不启动、停止、重启或代理采集服务，也不新增 HTTP 接口或采集生命周期控制。

## 验收

- [x] 插件根清单与 Codex 兼容清单都声明同一个本机网站地址。
- [x] 构建后的插件包保留网站地址，版本更新为 `0.1.1`。
- [x] Codex 插件详情页的“网站”从“不可用”变为可点击入口。
- [x] 点击入口只打开默认浏览器，不改写数据库和采集状态。
- [x] 网站服务不可用时，插件查询仍可用，入口不声称已启动服务。

## Comments

2026-11-01：用户确认采用“插件详情页入口 + 默认浏览器”，并明确插件不负责采集服务生命周期。先做最小验证；失败时再评估全局 MCP App。

2026-11-01：清单、构建与打包测试通过。源码外构建包 SHA-256 为 `3DB148BE7384F21B5C0ACB6256B5EDBC95E9659B73E414184D98A17B6C51669C`；本机 marketplace 与安装缓存已更新到 `0.1.1`。Codex 实际插件详情页显示“网站”链接，但当前客户端进程首次点击仍打开应用内浏览器。检查客户端配置后确认普通 URL 与本地 URL 使用独立偏好，已在本机桌面配置增加 `open-local-url-in-target-preference = "external-browser"`。需重启 Codex 让该设置进入运行态后再完成点击验收；暂不升级全局 MCP App。

2026-11-01：用户确认插件详情页链接可以正常跳转。宿主进程记录显示 `msedge.exe --single-argument http://127.0.0.1:8766/`，父进程为 ChatGPT 桌面进程；系统 `http` 与 `https` 默认处理程序均为 `MSEdgeHTM`，因此该入口已按默认浏览器打开。点击后没有新增插件侧服务控制：8766 仍由原有 Python 进程提供，`/api/status` 为 `running=true`，启用时间仍为 `1792940638.27711`。打包后的 MCP 查询测试使用独立临时数据库，不依赖 8766 服务；插件说明只声明既有网页入口，不声称会启动服务。

2026-11-01：本机“默认浏览器”由 Codex 桌面偏好 `open-local-url-in-target-preference = "external-browser"` 保证；插件清单本身不能设置宿主偏好。当前机器的一次点击验收已完成，但新配置或重置该偏好后，宿主可能改回应用内浏览器。该前提已写入交验记录，不把它误述为插件包自带行为。

2026-11-01：双轴复核发现 MCP `initialize.serverInfo.version` 仍是 `0.1.0`。已先补失败断言，再同步为 `0.1.1`；重新构建、重装后从安装缓存实测初始化返回 `0.1.1`，插件仍为启用状态。最终源码外 ZIP 为 `C:/Users/614/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/LocalPromptJournal/plugins/local-journal-0.1.1-r2-20261101-215057/local-journal.zip`，SHA-256 为 `79E1C23BBE471BFE7EC5566C59ECDBB2CB197A8C2D502C4B5DB8DB5A07207769`。
