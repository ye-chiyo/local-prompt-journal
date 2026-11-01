# 本机插件交验记录

日期：2026-10-28

- 名称：本机会话记录；标识：local-journal@local-journal-dev；版本：0.1.0。
- 源码：插件目录、构建工具，以及 Journal 新增的可选只读打开模式。现有写入模式继续默认启用。
- 部署：本机 marketplace 已注册，codex plugin add 返回安装成功；安装位置为 C:/Users/614/.codex/plugins/cache/local-journal-dev/local-journal/0.1.0。
- 构建：独立包与 ZIP 保存在源码外 LocalPromptJournal/plugins/local-journal-0.1.0。包包含必要读取代码和图标，不含真实日志、附件或数据库。构建时固定本机已测试 Python 解释器。
- 测试：14 项插件及相关行为测试通过；新增只读初始化涉及共享入口，因此随后完成全套 68 项测试，全部通过；mypy 检查 18 个源码文件通过。
- 插件验收测试从打包后的 MCP stdio 进程调用，使用独立事实验证中文命中、长原文分页、删除排除、错误输入和数据库不变；只读模式拒绝写入，缺库不创建目录。
- 安装后的进程实测：初始化成功；tools/list 返回六个预期工具；list_projects 对真实归档查询成功，仅核对分页元数据，未输出项目名或正文；进程退出 0，stderr 为空。
- 状态含义：archive_status 仅返回持久状态，明确 liveCollectorState=unknown。网页链接需要既有 8766 服务运行；插件数据库查询不依赖该服务。
- 正式服务未重启，启用时间未重设，正式数据未改写。当前聊天工具表未动态载入新插件，需在新 Codex 会话选择插件完成用户体验。尚未获得用户验收，未提交、推送或公开发布。

协议实现参考：https://modelcontextprotocol.io/specification/2025-11-25/basic/transports

2026-10-28 用户明确要求一次 commit，本记录随本轮实现统一提交。此前“未提交”的描述是该阶段的状态；正式服务更新及尚未完成的宿主体验仍按上文单独记录。

## 2026-11-01 网站入口最小验证

- 插件版本更新为 `0.1.1`，根清单和 Codex 兼容清单均在 `interface.websiteURL` 声明 `http://127.0.0.1:8766/`。
- 最终源码外构建包位于 `C:/Users/614/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/LocalPromptJournal/plugins/local-journal-0.1.1-r2-20261101-215057/local-journal.zip`，SHA-256 为 `79E1C23BBE471BFE7EC5566C59ECDBB2CB197A8C2D502C4B5DB8DB5A07207769`。此前构建的 MCP `initialize.serverInfo.version` 仍为 `0.1.0`，已先补失败断言，再同步为 `0.1.1` 后重新构建。
- 本机 `local-journal-dev` marketplace 已切换到 `0.1.1`，`codex plugin add` 安装到 `C:/Users/614/.codex/plugins/cache/local-journal-dev/local-journal/0.1.1`。
- 从重装后的安装缓存发起 MCP 初始化，返回 `serverInfo.version = "0.1.1"`，六个只读工具列表正常；`codex plugin list --marketplace local-journal-dev --json` 显示插件已安装且启用。
- 插件详情页实测版本为 `0.1.1`，“网站”从“不可用”变为可点击链接，地址为 `http://127.0.0.1:8766/`。
- 用户确认真实链接可以正常跳转。宿主进程记录为 `msedge.exe --single-argument http://127.0.0.1:8766/`，其父进程是 ChatGPT 桌面进程；系统 `http` 与 `https` 的默认处理程序均为 `MSEdgeHTM`。因此一次点击已进入默认浏览器，不再需要升级为全局 MCP App。
- “默认浏览器”由本机 Codex `[desktop]` 偏好 `open-local-url-in-target-preference = "external-browser"` 保证。插件清单不能设置宿主偏好；新配置、重装或重置偏好后仍可能回到应用内浏览器，这是当前最小方案的环境前提。
- 网站入口没有调用采集启动、停止、重启或代理接口。8766 仍由原有 Python 进程提供，查询时 `/api/status` 为 `running=true`，采集启用时间保持 `1792940638.27711`，网站 HTTP 返回 200。
- 打包后的 MCP 查询测试使用独立临时数据库，不依赖网页服务；插件说明只声明打开既有网页，不声称入口会启动服务。网站服务不可用时查询仍可用，入口也不会改变服务状态。
