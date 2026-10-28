# 本机 Codex 会话记录

最小本机应用：自带 SQLite 本地数据库，通过同版本 Codex App Server 的只读历史接口自动发现多个项目的会话并持续入库，按项目阅读完整会话，保留用户提示、AI 消息及来源实际返回的工具证据。无需手动下载或另行安装数据库。任务 01、02 已获用户验收；合并后的任务 03 于 2026-10-26 获用户明确“验收通过”，已登记完成。

2026-10-27 保留范围更新：用户要求当前正式库只保留对话及消息附件，删除“工具调用与最终结果”、不支持条目及各保存版本中的对应原始载荷。该策略在数据库中持久保存，后续自动采集不会重新入库工具。下文早期任务中保留全部工具证据的描述适用于未启用此策略的数据库；当前决策见 [ADR 0002](docs/adr/0002-dialogue-only-retention.md)。

用户已确认本轮通过并要求最终收尾：项目分页目录、独立回合阅读和只保留对话三阶段任务均登记完成，统一提交到本地 `codex/remaining-log-issues`，不自动 push。正式库已从清理前 2.57 GB 减为约 592 MB，保留当时全部 1,506 个版本；数据库会随新对话增长。47 项测试、类型检查、双轴复审和真实浏览器路径通过，当前运行与备份信息见 [最终交验记录](docs/verification/dialogue-only.md)。

显式清理命令（先停止此数据目录的采集服务，备份使用新的源码外路径）：

```powershell
python -m prompt_journal --data-dir 外部数据目录 prune-tools --backup D:/外部备份/新的目录/journal.sqlite3
```

清理包含所有历史保存版本、原始响应中的重复工具载荷及回合投影，再回收 SQLite 空闲空间。保留消息原文、消息原始对象、消息附件、版本身份及顺序，来源证据明确标注为消息摘录；不再提供完整协议响应或工具证据。用户／AI 消息正文内出现的工具名称与代码仍按原文保留。已有归档附件字节暂留，以便恢复独立数据库备份；备份及附件文件的空间不计入数据库回收量。恢复时先停服，使用备份替换同一数据目录中的 `journal.sqlite3`，保留原 `attachments` 目录；恢复也会还原备份时的采集策略。运行中的采集器会阻止清理，已有备份不会被覆盖，校验失败会回滚数据改写。

2026-10-26 当前交付：项目聚焦如实记录、查找和核对日志。任务 07（人工评价与纠正关联）和 08（提示改写版本与使用案例）已取消，07 未提交实现已撤回。01、02、03、05、06、09 已验收，04 并入 03；本轮按用户“完成剩下的 Issues”授权，在 `codex/remaining-log-issues` 实现 10 受管理删除、运行 11 日志全流程验证并完成首页布局反馈；用户于 2026-10-26 明确验收并要求 commit，已据此登记完成并一次提交。任务 11 已记录受控流程、已有真实证据回归、实时来源状态差异和 Windows 开销，不能据此宣称全部桌面格式或性能已认证；详见[当前任务列表](.scratch/local-prompt-journal/README.md)和[任务 11 交验记录](docs/verification/11-release-verification.md)。09 原提交 `1be3c26834332807af1cf7c368d04bd835a63dd7` 已集成 master，范围文档提交为 `c90e8d2`。本轮不改正式启用时间、不删除正式归档对话，不自动 push。

任务 03、04 合并为[多项目自动归档与持续同步](.scratch/local-prompt-journal/issues/03-capture-scope.md)，见[决策记录](docs/adr/0001-automatic-project-archive.md)。首次范围已确认：从启用后的下一个新回合开始，旧会话随后新开的回合也自动采集；跨启用时刻的旧回合及更早正文不回补。已经授权保存的旧记录继续保留。2026-10-28 用户确认桌面联动与登录监视器，当前用户计划任务已安装；真实 Codex 重启后自动恢复采集和网站的测试通过，详见[桌面联动交验记录](docs/verification/desktop-following.md)。

运行环境：Windows、Python 3.12+、桌面版 Codex。应用只使用 Python 标准库；不需要 API key、模型服务、npm 安装或远端数据库。真实验收版本及限制见 [验证记录](docs/verification/01-single-session-proof.md)。

### Codex 可执行文件查找

自动采集启动只读 Codex App Server 时，会按以下顺序查找可执行文件：

1. 环境变量 `CODEX_EXECUTABLE` 指定的文件（适合自定义安装位置）。
2. 当前进程 `PATH` 中的 `codex` 或 `codex.exe`。
3. Windows 桌面捆绑目录 `%LOCALAPPDATA%/OpenAI/Codex/bin/<版本>/codex.exe` 中最近修改的文件。

因此，桌面版 Codex 更新版本或服务进程继承旧 `PATH` 时，通常无需手动修改 `PATH`。也可以显式指定路径：

```powershell
$env:CODEX_EXECUTABLE = 'C:\Users\你的用户名\AppData\Local\OpenAI\Codex\bin\<版本>\codex.exe'
python -m prompt_journal run --port 8766
```

`CODEX_EXECUTABLE` 必须指向实际存在的文件。修改环境变量或更新 Codex 后，需要停止并重新启动本应用服务；已经运行的进程不会自动刷新环境变量。若仍无法找到来源，请先运行 `Get-Command codex`，检查显式路径和 `%LOCALAPPDATA%/OpenAI/Codex/bin/` 下是否存在 `codex.exe`，再查看页面中的来源错误。

## 使用

在本目录的 PowerShell 运行：

若终端当前位于其他目录，先执行 `Set-Location -LiteralPath 'D:\AI\日志项目'` 进入项目根目录，再运行下列命令；否则 Python 无法找到 `prompt_journal` 模块。

```powershell
# 首次启用自动采集与页面；从此刻之后新开始的回合读取正文。
python -m prompt_journal run --start-from-now --port 8766

# 后续重新启动：沿用已保存启用时间，自动补回停机期间的新回合。
python -m prompt_journal run --port 8766
# Ctrl+C 停止服务。关闭浏览器页面不会停止采集。

# 可选：当前 Windows 用户登录后待机；ChatGPT 桌面主进程运行时采集 Codex Local/Worktree。
python -m prompt_journal install-autostart
# 移除登录任务并停止当前监视器及其采集服务。
python -m prompt_journal uninstall-autostart

# 先检查用户选择的无敏感会话；不会恢复或执行历史任务。
python -m prompt_journal probe 会话ID

# 导入指定会话。重复导入会保留快照版本，当前时间线不会重复显示消息。
python -m prompt_journal import 会话ID

# 阅读及管理既有保存记录（不运行采集器）；Ctrl+C 关闭。
python -m prompt_journal serve

# 关闭应用后仍可查询、导出；这些命令不会连接 Codex。
python -m prompt_journal list
python -m prompt_journal show 会话ID
python -m prompt_journal export 会话ID --output C:/Users/614/AppData/Local/LocalPromptJournal/exports/session.json
```

默认数据目录：`%LOCALAPPDATA%/LocalPromptJournal/data/`，数据库为 `journal.sqlite3`。用 `python -m prompt_journal --data-dir 外部目录 ...` 更改。数据库与导出均拒绝写入本项目源码目录；Git 同时忽略 SQLite、JSONL、缓存与运行时产物。

应用自带 SQLite 数据库，无需另行安装。对话、工具记录、原始证据与修订会在采集服务运行时自动入库；重新打开页面后直接读取已保存记录。首次启用时只读取启用后开始的回合；旧会话后续新开的回合会自动采集，跨启用时刻的旧回合不回补。来源只提供整秒时，启用同秒无法区分先后的回合也不读取；开始时间未知会报告错误。页面关闭后，仍在运行的采集服务继续工作。

顶部只显示简短采集状态；数据库完整路径、采集说明和详细错误统一放在独立的 `/status` 页面。采集服务运行时自动保存，关闭浏览器后仍继续；停止采集服务后暂停新记录入库。服务重启沿用同一数据库即可继续查看和采集，不需要先下载、导出或重新导入。当前本机正式服务使用的数据文件是 `C:\Users\614\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\LocalPromptJournal\data\journal.sqlite3`；8767 演示服务使用单独的测试数据库，不是正式会话记录。

Windows 通过当前用户计划任务 `LocalPromptJournal ChatGPT Desktop Monitor` 登录启动隐藏监视器；安装命令立即通过任务调度器启动它，运行独立于 Codex，重装会移除旧 Startup 快捷方式。监视器使用显式的已有正式数据库物理路径，避免 MSIX 应用内外 AppData 重定向产生不同数据库。默认目录同时检查普通与当前包缓存路径；若发现多个不同数据库则要求使用 `--data-dir` 明确选择。监视器识别 ChatGPT 主进程（通过实际命令行忽略 renderer 等子进程，包括残留的孤立辅助进程）；应用已运行时立即启动采集，主进程退出后停止，采集器异常退出时自动重启。窗口关闭但桌面主进程仍在时会继续采集。它仅连接本机 Codex 历史接口，不读取普通 ChatGPT 对话；Cloud 会话不在支持范围。安装与移除分别使用 `install-autostart` 和 `uninstall-autostart`；仅影响当前 Windows 用户。详情见[桌面联动决策](docs/adr/0003-desktop-following-collector.md)。

日常查看不需要通过 AI：双击 Windows 桌面上的 **Codex 日志**，或在开始菜单查找 **Codex 日志**，会用默认浏览器打开 `http://127.0.0.1:8766/`。当前桌面入口实际位于 `D:\桌面\Codex 日志.lnk`。入口只打开网站，仍沿用桌面应用主进程运行时提供采集及网页服务的规则；完全退出 Codex 后网站随服务停止，已保存记录保留。可通过 `python -m prompt_journal install-shortcuts` 安装或恢复两个入口；命令不停止采集器，重复安装不会增加重复图标，也不会覆盖同名的无关入口。2026-10-28 已完成安装、网址及 HTTP 200 核对，用户明确确认可以打开。

实机重启测试使用 Windows PowerShell；默认只预检查，不关闭应用。显式 `-Run` 会创建当前用户的一次性隐藏计划任务，等待 20 秒后强制结束当前安装包路径对应的 Codex 桌面进程，再重新打开应用，检查采集服务是否自行停止与恢复。它会中断当前桌面任务，应在允许重启时运行：

```powershell
Set-Location -LiteralPath 'D:\AI\日志项目'
# 只检查应用、监视器、来源、服务端口及数据目录，不重启。
powershell.exe -NoProfile -File .\tools\test_desktop_restart.ps1
# 真正执行一次重启，测试进程独立于 Codex 运行。
powershell.exe -NoProfile -File .\tools\test_desktop_restart.ps1 -Run
```

命令返回报告目录，默认在 `%LOCALAPPDATA%\LocalPromptJournal\verification\desktop-restart-<时间>-<随机标识>`；`result.json` 和 `result.md` 随步骤更新，最终 `PASS`／`FAIL` 是实际测试结果，`RUNNING` 只表示尚在执行。测试不手动启动监视器／采集器，也不改变 `enabledAt`；恢复后要求新的采集成功时间及首页 HTTP 200。失败仍尝试重开桌面应用，报告保持失败。计划任务注册失败会在关闭应用前中止；执行完会删除临时任务。该测试不代替 Windows 登录启动、正常退出或新增对话正文入库验收。

`probe` 无预期清单时只做能力探测并返回退出码 1，表示尚未验收；不会将“能够连接”误报为“样本通过”。薄真实契约检查需提供**事先独立定义**的完整样本清单：

```powershell
python -m prompt_journal probe 会话ID --page-size 1 --expected C:/Users/614/AppData/Local/LocalPromptJournal/acceptance/expected-desktop-sample.json --report C:/Users/614/AppData/Local/LocalPromptJournal/acceptance/real-contract.json
```

真实清单包含 `definedBeforeImport: true`、`thread.id`、`page.hasMore: false`，及 `turns[].id/status/messages[]`。消息使用实际桌面 `userMessage` / `agentMessage` 的身份、文本与阶段；不能从本应用输出反向生成验收预期。

## 查询与证据

- Python 公开接口：`Collector.start/stop/status`、`Journal.projects`、`import_session`、`session`、`sessions`、`export_session`；`CodexHistory` 是最外部 Codex 数据源边界。
- HTTP：`GET /api/status`、`GET /api/projects`、`GET /project/<项目身份>`、`GET /api/sessions`、`GET /api/session/<id>`、`GET /session/<id>`、`GET /export/<id>`、`GET /evidence/<id>/<index>`。
- 相同会话 ID 来自多个来源实例时，查询须指定 `?source=<instance>`，CLI 使用 `--source-instance`，防止合并不同来源。页面链接自动携带身份。
- 导出是一个自包含 UTF-8 JSON，含 `schemaVersion`、`session`、`evidence`。每条消息的 `evidenceRef` 是该文件内的 JSON Pointer。只保留对话的数据库使用明确标注的原始消息对象摘录、原定位与响应校验信息；未启用该策略的数据库保留请求参数、实际响应、原始解码行、SHA-256 与采集时间。`raw` 为 UTF-8 解码后的接口行，换行遵循 Python 文本流规范，并非原生数据库的逐字节备份。
- 保留原始消息 ID、回合 ID、来源实例、源时间、状态与消息顺序。未知时间／阶段显示未知；非文本消息保留原始引用，附件逐条显示归档或缺失状态。AI 原文按纯文本显示，不执行 HTML、命令、工具或附件。

每个回合拥有独立页面，只读取该回合，连续展示其用户、AI 过程及最终消息，保留原文和来源顺序。当前正式库只保留对话及消息附件，已移除工具板块；用户粘贴的文档、AI 消息及正文内的代码保持原文，保存版本与消息来源摘录仍可核对。未启用该策略的数据库继续兼容默认折叠的工具最后结果视图。

首页选择项目后，进入按会话分页的目录，每页固定 6 个会话，最后一页显示剩余会话；`offset` 按会话计算。一个会话完整留在同一页，回合目录首批加载 30 条元数据，较长会话通过“加载更多回合”继续查看。旧项目链接中的 `limit=30` 仍按每页 6 个会话显示；独立会话目录保留原有回合分页。目录只读取元数据；点击“回合 1”等入口直接打开 `/session/<会话>/turn/<回合>?source=<来源>`，不再预先读取或展示整段会话，也不扫描其他会话正文构建关系。阅读页提供上一回合、返回目录、下一回合。会话仍按开始时间升序，各会话内部保持来源回合顺序。目录和阅读页不包含大块状态卡或搜索表单，搜索通过顶部独立入口访问，命中直接定位相应回合与保存版本。旧会话地址作为轻量目录兼容入口，旧命中和 `#turn-N` 锚点可跳到独立回合。

回合正文按内容摘要去重并压缩，与保存版本关联；升级首次启动回填历史回合投影，输出数量进度，后续保存与目录同事务更新。旧完整会话 API、来源证据和导出保留，项目、回合与按需消息／工具读取各走独立查询。页面每 1.5 秒检查更新，阅读中的选择和搜索输入仍会保留。真实库性能与验证见[独立回合交验记录](docs/verification/turn-pages.md)。

新增快照使用无损压缩，保留消息、工具结果、原始证据与所有保存版本。旧数据库可继续读取；停服后可压缩已有快照并回收空闲页，必须指定新的源码外备份文件：

```powershell
python -m prompt_journal --data-dir '你的正式数据目录' compact --backup 'D:\日志备份\新的压缩前备份.sqlite3'
```

压缩先做一致性备份，再逐快照校验解压后的原始字节，最后回收空间；不删除中间历史。压缩后的快照由新版程序读取，回退旧程序应恢复压缩前的独立备份。真实库性能、减量与浏览器验证见[项目目录交验记录](docs/verification/project-session-catalog.md)。

导出在原有字段之外增加 `session.tools` 和 `session.unsupportedItems`，不移除消息及原始证据。`tools` 使用当前正式接口的原子条目身份 `(来源实例, 会话, turnId, id)`，参数与结果同属该条目，不按文本或位置合并。`evidenceRef` 指向原始工具载荷，`order` 保留来源顺序；页面、公开查询和导出使用同一保存记录。`sourceStatus`、`sourceSuccess` 保留来源字段；展示 `status` 遇到错误／非零退出码为失败，声称完成但未取得结果为未知。`businessOutcome` 始终未知，不把执行完成当作业务成功。

支持正式接口中的 `commandExecution`、`mcpToolCall`、`dynamicToolCall`、`functionCallOutput`。独立函数输出没有请求身份时单独显示，不猜配请求。来源未保证完整性时显示未知；缺结果或来源结构化截断标记标为部分内容，正文中的截断提示仅报告是否截断未知。长输出不缩写；其他类型显示不支持并链接完整原始证据。来源没有独立返回的包装函数或嵌套调用不构造调用树，只按正式字段解析关系，不解析输出文字中的命令、句柄或子任务关系。

## 任务 05：关联执行证据（已验收完成）

会话内“关联会话”展示来源提供的子 agent、分叉及协作关系。身份来自 `parentThreadId`、`forkedFromId`、正式子 agent 来源字段、`subAgentActivity.agentThreadId` 或 `collabAgentToolCall`；活动关联不自动等于直接父子。已归档目标可进入自己的项目、消息与回合；缺身份、未归档、来源不可访问时明确说明。枚举已取得的关系元数据即使没有范围内正文也会保存为无正文的字段投影，经 `/relation-evidence/<id>` 核对；预览和旧正文仍不保存。查看和导出均只读本地保存，不连接来源或扩大首次范围。

每回合的“执行过程”增加“后台执行证据”，以来源实例、会话、回合、条目 ID 追踪命令保存修订。展示取得的 PTY 句柄、输出、退出码与每次原始证据；相同命令或复用句柄不合并。来源声称完成但没有退出码时仍为未知。当前历史协议没有独立轮询记录，句柄本身也不能证明后台运行；界面不伪造此类链路。修订只表示保存观察顺序，不代表执行因果。

根据用户 2026-10-26 的体验反馈，页面移除“结构化导出”和“选择导出范围”，日常使用以自动入库、直接阅读为主。关联会话在同一数据库内分别保存，是否入库遵守既有采集范围，不依赖页面或导出选择。

可选的 CLI／HTTP 结构化导出保留兼容性，默认单会话；显式使用 `export 会话ID --include-related --output 源码外路径` 或 `/export/<id>?related=1` 才包含一层已归档关联会话（父／子／分叉／交互）。导出 `related` 各自保留会话、修订与证据，`exportScope` 列明包含和未包含目标；不递归包含孙会话。没有包含所有者的关系证据引用为 null，`ownerEvidenceRef` 仍定位所有者自己的保存文档；包含后的 `evidenceRef` 指向整个导出文件。元数据投影经 `/metadata/<id>` 核对，明确区别于完整原始响应。

任务 05 于 2026-10-26 获用户明确“审核通过”，已登记完成，包含自动入库的页面调整。自行验证与真实来源边界见 [交验记录](docs/verification/05-execution-topology.md)。真实后台独立轮询、真实分叉正文及全部版本覆盖尚未认证。

## 任务 06：中文正文搜索（已验收完成）

首页、项目页和会话页均有搜索表单，项目页默认当前项目，会话页默认当前会话。按项目身份与来源实例／会话身份限定范围，组合选择取交集；主会话不包含关联会话正文。同名或同文记录不合并。仅查询本地已保存内容，不连接 Codex、不回补历史。

搜索结果卡片按用户体验反馈简化：展示可读的项目、会话、内容类型及原文片段，部分／完整性未知记录保留必要提示。项目哈希、来源实例、会话／回合／条目 ID、协议类型及精确保存版本不在卡片正文展示；后端身份、公开查询及原始证据仍保留，点击定位继续固定到实际保存版本。

采用区分大小写的连续原文子串：`SQLite 中文归档` 不等于 `sqlite 中文归档`，空格、换行、标点原样匹配，`%`、`_`、`*` 等均为普通文本；全空白查询提示输入。搜索全文之后才生成命中位置片段，每条实际消息／工具列一条结果，当前修订替代旧修订。按会话开始时间、来源实例、会话 ID、来源条目顺序排列，每页 30 条，显示总数与翻页；并发更新时重新查询当前保存视图。

覆盖用户规范化文本、AI 过程／最终及阶段未知消息、命令 `aggregatedOutput`、MCP `result.content` 文本及 `structuredContent` 中的字符串值、动态工具 `contentItems` 的 `text/inputText`、独立函数 `output` 字符串、工具 `error` 字符串或 `error.message`。不同文本块不跨块拼词。不搜索标题、工具参数、协议键名、关系元数据、未支持事件或附件。不恢复隐藏思维、截断缺失部分或来源未返回文本。无结果仅表示当前范围内已保存且支持检索的文本没有命中。

点击结果固定到命中保存版本，定位实际条目并展开执行过程及工具；高亮按纯文本处理，原文不执行 HTML。可查看全部已取得原文、完整性状态与原因、对应版本的原始证据，并返回最新保存内容。页面搜索自动反映新的入库内容；无需同步、导入或重建索引，服务重启沿用同一数据库即可继续搜索。搜索直接扫描当前保存快照，未建设分词、语义、模糊或相关性算法，也不搜索所有历史版本。

公开 Python：`Journal.search(query, project=None, thread=None, instance=None, offset=0, limit=30)`；HTTP：`/api/search?q=词组&project=项目身份&session=会话ID&source=来源实例`，分页用 `offset`、`limit`（1—100）。页面 `/search` 由表单自动携带身份；不要用同名标题代替身份。`session(..., saved_at=...)` 可核对命中版本，旧证据链接保持兼容。任务 06 于 2026-10-26 在结果卡片简化后获用户明确“审核通过”，已登记完成。验证边界及体验入口见[任务 06 交验记录](docs/verification/06-chinese-search.md)。

## 当前边界

自动发现当前 `codexHome` 中正式接口可见的本机会话（含已归档会话及全部已知来源类型），依据来源 `projectId`，否则依据 `cwd` 分项目；均缺失时归入“项目未知”，身份还包含来源实例。不扫描其他应用或猜测其他 Codex 安装目录。枚举使用 `useStateDbOnly=true`，避免默认的来源元数据修复写入。列表附带的预览仅在请求内短暂存在，不保存为正文或原始证据。默认每轮完成后等 3 秒再次检查，可用 `--interval` 调整；每轮重新取得范围内回合及条目，不用最近更新时间作为完成条目的永久断点。旧会话只有来源更新时间进入范围才读取无正文回合元数据；没有可靠回合时间时显示错误。

自动读取只使用不含正文的回合元数据及限定回合的完整条目分页；手动导入仍核对完整回合和条目两种分页。分页冲突、格式不支持、读取或保存失败时保留上次成功快照，随后重试。保存成功才成为进度；同一目录只允许一个采集器。来源新快照缺少已保存的范围内条目时报告缺失并保留旧快照，不声称恢复成功。变化后的快照保留独立修订，完整导出的 `revisions` 包含旧会话视图、原始证据及文档内证据引用。没有新变化时不生成重复修订。

命令白名单仅含 `initialize`、`thread/list`、`thread/read`、`thread/turns/list`、`thread/items/list`，及握手通知。不会调用 `thread/resume`、`turn/start`、注入、历史命令或模型。新增 Python 组件不包含远端客户端；查看服务只绑定 `127.0.0.1`，没有外部脚本、字体或遥测。启动原生 App Server 时显式关闭 analytics、feedback 和 OTel 导出，并将子进程的 HTTP/HTTPS/ALL 代理覆盖为本进程保留、但不监听的本机端口，清空代理绕过列表，防止继承系统转发代理。当前版本已实测本机失败请求不影响历史读取；这是针对代理客户端的出口防护，并非系统防火墙，不能据此认证任意未来原生版本。

所有额外条目保留在原始证据中；子会话关系仅打开已授权保存的快照，不做人工标注。`source.gaps` 和 `source.notDisplayedTypes` 明示限制。历史快照保存在本机数据库中，修订可从完整导出核对；受管理删除及排除入口见下节，尚未提供跨设备迁移。当前真实工具样本只认证了命令与 MCP；动态工具与独立函数输出只有固定协议样本验证，不能据此认证真实来源覆盖率。详情见 [任务 02 验证边界](docs/verification/02-test-boundary.md) 和 [任务 03 交验记录](docs/verification/03-automatic-archive.md)。

## 开发验证

```powershell
python -m unittest discover -s tests -v
python -m mypy
```

应用运行不依赖 mypy。测试只替换外部 Codex 协议服务，经过真实导入、SQLite 保存、重开、HTTP 页面及 JSON 导出。真实数据不在测试或源码中。测试边界及样本定义见 [边界说明](docs/verification/01-test-boundary.md)。

## 任务 09：附件与可选离线会话包（已验收完成）

自动采集保存正式附件字段可取得的原字节，不用逐条下载。对应消息／工具条目显示“已归档附件”或具体缺失原因，点击本机副本可查看图片或保存普通文件；页面不执行附件内容。已归档副本放在 `--data-dir` 内源码外的受管理目录，原文件移动、服务重启和重复同步后仍可核对。内容同名不覆盖，来源关系分别保留。

只处理明确类型和字段，不解析正文／Markdown 链接或命令输出中的路径，不扫描磁盘，不联网补下载。远端、fileId 无本机解析接口、原文件不存在或保存失败均如实说明。老快照未曾归档的附件不使用今天的文件补成历史版本；本机路径没有来源校验时，说明这是归档时读取的文件，不能证明消息发生时的版本。对话文本与附件分别报告，不宣称完整原生备份。

原 `export` CLI 与 `/export/<id>` 继续返回兼容的 schemaVersion 1 JSON。需要可移动的附件和证据时，可选新命令（输出位置须在源码外）：

```powershell
python -m prompt_journal --data-dir 外部数据目录 bundle 会话ID --output C:/外部目录/session-bundle.zip
python -m prompt_journal --data-dir 外部数据目录 bundle 会话ID --include-related --output C:/外部目录/related-bundle.zip
```

HTTP 为 `/bundle/<id>`，显式一层使用 `?related=1`；多来源同 ID 时同样要求 `source`，CLI 使用 `--source-instance`。默认仅当前会话，显式一层沿用任务 05 的已归档关联范围，不递归，不在导出时连接来源。普通阅读页没有新增导出表单，导出不是自动保存前提。

解压 ZIP 后，`session.json` 保留完整既有导出、原始证据及修订，`manifest.json` 的 `bundleVersion=1` 列出附件对应关系、实际文件校验和缺失项，`attachments/` 保存原字节，`README.txt` 提供离线定位及 PowerShell 校验操作。`bundlePath` 相对解压目录；`evidenceRef` 定位 session.json 内证据，来源原路径／URL 仅供溯源。整目录移动后无需原数据库、原附件、日志服务或网络即可核对。

任务 09 在独立分支和受控数据中验收，原提交现已快进集成 master。07、08 已取消；与受管理删除的组合验证现见[任务 11 记录](docs/verification/11-release-verification.md)，本轮交付已于 2026-10-26 获用户明确体验确认。真实来源目前只核对本机 schema、已有授权证据和当前新回合的稳定消息／命令；真实样本无附件，MCP 附件等仍只有受控协议验证。实际边界见 [任务 09 验证记录](docs/verification/09-offline-evidence-export.md)。

## 任务 10：受管理删除与删除排除（已验收完成）

会话页点击“删除此会话的受管理日志”，核对会话及来源和删除范围后确认。应用清理该来源会话的正文、工具、全部来源修订、原始证据、搜索内容和附件引用；其他会话仍引用的共享附件保留。删除只影响本应用，不改变 Codex 原会话、原附件或用户另存的导出包，不宣称取证级磁盘擦除。

删除后持久保留排除，持续采集及服务重启都不会自动带回此会话。顶部“删除排除管理”可查看状态并显式解除排除；之后自动采集仍遵守原启用时间，不恢复已删除的历史副本、不回补原范围之前正文。附件清理失败时显示“清理未完成”及实际原因，保持排除；修复文件占用／权限后可重试，应用重开也会重试，完成前不能提前解除排除。

公开 Python：`Journal.delete_session(id, instance=None)`、`restore_session(...)`、`exclusions()`；HTTP 管理入口 `/manage/exclusions`，查询 `/api/exclusions`。CLI 示例（只对自己明确选择的受管理会话执行）：

```powershell
python -m prompt_journal exclusions
python -m prompt_journal delete 会话ID --source-instance 来源实例 --yes
python -m prompt_journal restore 会话ID --source-instance 来源实例
```

多个来源具有相同会话 ID 时必须明确来源；页面自动携带身份。删除、保存与附件清理以同一 SQLite 写锁协同，读取期间的删除不能被迟到快照覆盖。验证及故障边界见[任务 10 记录](docs/verification/10-managed-deletion.md)。

## 任务 11：全流程演示与运行边界（已验收，保留验证边界）

本轮提供固定中文、四会话／两项目的无敏感演示。用新的源码外目录即可重建，工具只使用受控来源，不读取真实 Codex、不操作正式数据：

```powershell
python -X utf8 tools/verify_release_flow.py --output 'D:\AI\日志演示-新的目录'
python -m prompt_journal --data-dir 'D:\AI\日志演示-新的目录\data' serve --port 8791
# Ctrl+C 停止演示服务。
```

工具验证自动发现、项目顺序、中文搜索、工具修订、来源中断及重启补回、共享附件删除／排除／恢复，并留下已移动原附件仍可读的归档及离线包。正式采集仍使用前文 `run`，沿用同一正式数据目录，不重新设置启用时间。

当前桌面活动回合视图与独立历史接口对同一回合分别返回 `inProgress`／`interrupted`，稳定条目及证据匹配，状态一致性未通过。100ms 高频受控轮询的采集延迟中位数 159ms、P95 217ms。启用条件的父加来源进程单核等效 CPU 中位数为 62%，包含生成器、采集器、受控来源及每 5ms 调用公开 `Journal.session()` 的观察者；停用条件没有同等观察者，CPU 工作负载不对称，差量不能归因于纯采集器。不宣称低开销，正式默认仍为 3 秒。真实模型回合耗时和物理磁盘写入尚未测量，真实附件仍未认证。详见[完整记录、量值及复现说明](docs/verification/11-release-verification.md)。

## 本地插件

已提供“本机会话记录”本地插件：在 Codex 中按需查询项目、会话、回合和中文正文，复用已有归档数据库。安装、依赖及使用方式见 [插件说明](plugins/local-journal/README.md)，验证范围及待验收状态见 [插件交验记录](docs/verification/local-plugin.md)。

项目归档首页为每个项目提供“删除项目”入口。确认页列出完整项目路径和当前全部已归档会话，确认后跨所有目录页删除这些受管理记录并设置会话删除排除；以后新建会话仍按原采集规则归档。确认范围发生变化时须重新核对。同名但来源或路径不同的项目独立处理。验证与交付状态见 [项目删除交验](docs/verification/project-deletion.md)。
