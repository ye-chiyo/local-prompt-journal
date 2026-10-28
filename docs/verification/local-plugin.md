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
