# 任务 01 真实会话验证记录

日期：2026-10-25（Asia/Shanghai）。范围：`.scratch/local-prompt-journal/issues/01-single-session-proof.md`。真实样本与公开路径已通过；代码审查完成后再登记任务完成。

## 真实入口与样本

本机 PATH 中 `codex.exe` 与正在运行的桌面 App Server 使用同一可执行文件，版本 `codex-cli 0.164.0-alpha.11.1`。默认 daemon 控制 socket 探测返回连接失败（Windows 错误 10050）；没有启动、重启或修改桌面 daemon。采用同版本可执行文件的 `app-server --stdio`，使用已有本机 Codex home，从正式历史接口读取存储，不附加到正在运行的对话。

实测成功的方法为 `initialize`、`thread/read`、`thread/turns/list`、`thread/items/list`。回合读取显式设置 `itemsView: full`，条目读取采用 `sortDirection: asc`，遍历 `nextCursor` 至 null。未调用恢复、开始回合、注入或执行接口。客户端拒绝非白名单方法及服务端执行请求；原生进程 analytics、feedback、OTel 导出显式关闭。

官方协议与生成模式的来源：[App Server 官方文档](https://learn.chatgpt.com/docs/app-server)。已从当前安装版本生成实验接口 JSON Schema，保存在运行时目录 `probe-schema/`，用于核实字段，而非以文档声明代替实测。

用户已选择本项目此前的规格／工程配置会话作为无敏感样本：`01a17191-9368-7082-9d36-804621988b6d`。导入器实现之前，独立使用桌面 `read_thread` 取得完整 5 个回合、38 条消息的 ID、原文、阶段和回合状态，预存核对清单。清单 `page.hasMore` 为 false；不从导入器输出构造预期。

| 项目 | 独立预期 | 正式接口及应用结果 |
| --- | --- | --- |
| 回合 | 5 | 5；身份与状态逐一一致 |
| 用户原文 | 11 | 11；身份、原文一致 |
| AI 过程消息 | 17 | 17；身份、原文、commentary 阶段一致 |
| AI 最终回答 | 10 | 10；身份、原文、final_answer 阶段一致 |
| 总来源条目 | 非完整性判断依据 | 108；另有 70 条非聊天条目保留在原始证据 |
| 回合跨页 | 页大小 1 | 5 页；没有遗漏、摘要替代或重复展示 |
| 条目跨页 | 页大小 1 | 108 页；与完整回合的消息集合、身份、阶段一致 |
| 公开导出证据 | 每条消息可追溯 | 38 个 JSON Pointer 均解析到原始条目；原始响应与哈希一致 |

该会话仍有实际存在的 rollout JSONL，大小 1,345,807 字节；正式接口也可为这种存储提供分页读取。**本次没有认证全部桌面存储后端，尤其不将该结果外推为新分页数据库存储、远端／云端会话或所有未来版本的兼容认证。** 产品适配器只在两个完整历史接口均可用、两种结果一致时发布快照。

## 本机闭环

使用 Python 标准库实现了正式接口适配、SQLite 原始证据与快照保存、公开查询、回合时间线、原始证据入口及自包含 JSON 导出。

运行时根目录为 `%LOCALAPPDATA%/LocalPromptJournal/`。此桌面宿主将该目录解析为：

`C:/Users/614/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/LocalPromptJournal/`

真实清单、历史、截图、第三方检出与导出均在此目录，源码仅保存程序、人造测试和去内容化的验证结论。数据库与 CLI 导出拒绝写入源码目录。没有修改用户的 Codex 会话、hooks、配置文件或模型设置。

以公开 CLI 导入选定会话后，通过 HTTP 查询及导出与独立清单比较；结束查看进程、启动新进程后重新查询，结果相同。应用保存来源实例、版本、会话／回合／条目 ID、实际可取得的时间、源顺序、回合状态、采集时间及完整原始载荷。多来源同 ID 不合并。重复导入生成可追溯快照，当前时间线不重复展示。

已运行 `tools/verify_saved_session.py`，它只启动应用进程并访问公开 HTTP，不读取私有 SQLite 表。结果：所有布尔检查通过；38 条消息、108 条来源条目、导出 JSON 1,401,854 字节。检查包含新进程重开、逐字原文及阶段、全部证据引用、原始载荷 SHA-256、实际响应一致性、页面证据链接可访问。最初用子串计数页面链接会把历史正文中的相同短语也计入；已改为解析真实 `<a href>` 并逐个读取链接，非放宽验收。

真实内置浏览器已操作：会话列表 → 选定会话 → 时间线 → 展开版本与缺口 → 结构化导出入口。截图保存为 `acceptance/timeline-desktop.png`、`acceptance/source-capabilities.png`。导出端点保存的自包含文件可离线核对；浏览器点击导出入口不作为已落盘文件的唯一证明，以公开端点实际下载和内容核对补充。

页面以纯文本呈现历史中的 HTML、代码和链接，不执行它们；没有脚本、外部字体或资源请求，CSP 限制资源来源。服务只绑定 `127.0.0.1`，拒绝非本机 Host 与跨源 Origin，查询／查看期间不连接 Codex。

## 仅一个复用候选

从原有候选中只检查 AgentXRay 的 **Codex 旧 JSONL 适配能力**：版本 `1.24.0`，实际检出 commit `f409ae94c395fc59b578f3e44b9d465a7683726e`。未安装或启动其完整看板，没有调用模型能力，也没有复制第三方源码进入本项目。

在本机直接运行该版本 `lib/inspect.normalizeRecords`，输入同一个选定会话的真实 rollout 文件：375 条原始记录、154 条规范化条目、34 条工具请求及 34 条结果，适配器自己的 `issues` 为空。然而与独立桌面清单比较，预期 38 条消息中只有 **33 条原文匹配**；来源 ID 匹配 22 条；其 41 条用户／助手文本条目中全部没有消息阶段字段，另含不属于预期可见消息的条目。

结论：任务 01 **不采用**该适配器。适配器自身“无问题”不等于满足本任务的原文与阶段契约；仅凭候选 README 也不能认证当前桌面。结论只限这项适配能力，不评价其完整看板或其他能力。

## 可重跑证据

运行时 `acceptance/` 中保留：

- `expected-desktop-sample.json`：实现前定义的独立桌面消息清单。
- `raw-readonly-probe.json`、`readonly-probe-report.json`：首次正式接口探测及比较。
- `real-contract.json`：可重跑的薄真实连接契约结果。
- `public-path-report.json`：公开查询／导出及进程重开结果。
- `agentxray-reuse-report.json`：唯一候选的同样本实测比较。
- 两张真实浏览器截图。

运行时 `exports/` 中的 `session-01a17191.json`（CLI 导出）与 `http-session-01a17191.json`（公开 HTTP 导出）均可离线打开。所有消息通过 `evidenceRef` 返回同一文件内的原始记录。

## 已知缺口

任务 01 仅提供单次手动快照及消息展示。非聊天条目类型实际观察到 commandExecution、fileChange、mcpToolCall、reasoning、subAgentActivity、webSearch；它们保留原始载荷，未完成工具语义、嵌套／后台关联或子会话浏览验收。无法取得的时间／阶段保持未知。附件尚未复制，不能称为附件备份；源中已丢弃或隐藏的内容不可恢复。没有全格式、全平台或零性能开销承诺。

这些缺口在界面和导出中可见，对应后续任务。02–11 的文件、依赖和验收范围不变，本次不执行它们。
