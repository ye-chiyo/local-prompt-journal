# 本机 Codex 会话记录

最小本机应用：自带 SQLite 本地数据库，通过同版本 Codex App Server 的只读历史接口自动发现多个项目的会话并持续入库，按项目阅读完整会话，保留用户提示、AI 消息及来源实际返回的工具证据。无需手动下载或另行安装数据库。任务 01、02 已获用户验收；合并后的任务 03 于 2026-10-26 获用户明确“验收通过”，已登记完成。

任务 03、04 合并为[多项目自动归档与持续同步](.scratch/local-prompt-journal/issues/03-capture-scope.md)，见[决策记录](docs/adr/0001-automatic-project-archive.md)。首次范围已确认：从启用后的下一个新回合开始，旧会话随后新开的回合也自动采集；跨启用时刻的旧回合及更早正文不回补。已经授权保存的旧记录继续保留。Windows 登录自启动未获确认，本应用不安装启动项。

运行环境：Windows、Python 3.12+、桌面捆绑的 `codex.exe` 位于 PATH。应用只使用 Python 标准库；不需要 API key、模型服务、npm 安装或远端数据库。真实验收版本及限制见 [验证记录](docs/verification/01-single-session-proof.md)。

## 使用

在本目录的 PowerShell 运行：

若终端当前位于其他目录，先执行 `Set-Location -LiteralPath 'D:\AI\日志项目'` 进入项目根目录，再运行下列命令；否则 Python 无法找到 `prompt_journal` 模块。

```powershell
# 首次启用自动采集与页面；从此刻之后新开始的回合读取正文。
python -m prompt_journal run --start-from-now --port 8766

# 后续重新启动：沿用已保存启用时间，自动补回停机期间的新回合。
python -m prompt_journal run --port 8766
# Ctrl+C 停止服务。关闭浏览器页面不会停止采集。

# 先检查用户选择的无敏感会话；不会恢复或执行历史任务。
python -m prompt_journal probe 会话ID

# 导入指定会话。重复导入会保留快照版本，当前时间线不会重复显示消息。
python -m prompt_journal import 会话ID

# 只查看既有保存记录（不运行采集器）；Ctrl+C 关闭。
python -m prompt_journal serve

# 关闭应用后仍可查询、导出；这些命令不会连接 Codex。
python -m prompt_journal list
python -m prompt_journal show 会话ID
python -m prompt_journal export 会话ID --output C:/Users/614/AppData/Local/LocalPromptJournal/exports/session.json
```

默认数据目录：`%LOCALAPPDATA%/LocalPromptJournal/data/`，数据库为 `journal.sqlite3`。用 `python -m prompt_journal --data-dir 外部目录 ...` 更改。数据库与导出均拒绝写入本项目源码目录；Git 同时忽略 SQLite、JSONL、缓存与运行时产物。

首页、项目页与会话页顶部显示当前实际使用的数据库完整路径及采集状态，会话页显示最近入库时间。采集服务运行时自动保存，关闭浏览器后仍继续；停止采集服务后暂停新记录入库。服务重启沿用同一数据库即可继续查看和采集，不需要先下载、导出或重新导入。当前本机正式服务使用的数据文件是 `C:\Users\614\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\LocalPromptJournal\data\journal.sqlite3`；8767 演示服务使用单独的测试数据库，不是正式会话记录。

`probe` 无预期清单时只做能力探测并返回退出码 1，表示尚未验收；不会将“能够连接”误报为“样本通过”。薄真实契约检查需提供**事先独立定义**的完整样本清单：

```powershell
python -m prompt_journal probe 会话ID --page-size 1 --expected C:/Users/614/AppData/Local/LocalPromptJournal/acceptance/expected-desktop-sample.json --report C:/Users/614/AppData/Local/LocalPromptJournal/acceptance/real-contract.json
```

真实清单包含 `definedBeforeImport: true`、`thread.id`、`page.hasMore: false`，及 `turns[].id/status/messages[]`。消息使用实际桌面 `userMessage` / `agentMessage` 的身份、文本与阶段；不能从本应用输出反向生成验收预期。

## 查询与证据

- Python 公开接口：`Collector.start/stop/status`、`Journal.projects`、`import_session`、`session`、`sessions`、`export_session`；`CodexHistory` 是最外部 Codex 数据源边界。
- HTTP：`GET /api/status`、`GET /api/projects`、`GET /project/<项目身份>`、`GET /api/sessions`、`GET /api/session/<id>`、`GET /session/<id>`、`GET /export/<id>`、`GET /evidence/<id>/<index>`。
- 相同会话 ID 来自多个来源实例时，查询须指定 `?source=<instance>`，CLI 使用 `--source-instance`，防止合并不同来源。页面链接自动携带身份。
- 导出是一个自包含 UTF-8 JSON，含 `schemaVersion`、`session`、`evidence`。每条消息的 `evidenceRef` 是该文件内的 JSON Pointer；`evidence` 保存请求参数、实际响应、原始解码行、SHA-256 与采集时间。`raw` 为 UTF-8 解码后的接口行，换行遵循 Python 文本流规范，并非原生数据库的逐字节备份。
- 保留原始消息 ID、回合 ID、来源实例、源时间、状态与消息顺序。未知时间／阶段显示未知；附件未备份，非文本消息标记部分内容。AI 原文按纯文本显示，不执行 HTML、命令、工具或附件。

每回合默认连续展示用户、AI 过程及最终消息，保留对话原文与彼此的来源顺序。工具和其他非对话条目集中在回合末默认折叠的“执行过程”中，组内按来源顺序排列；展开后仍可点击“工具执行”查看参数、全部已取得结果、错误、状态及原始证据。工具读取的技能或配置文档正文保留在对应结果里；用户粘贴的文档、AI 对技能的解释仍直接展示，不按关键词隐藏。分组后的页面位置不代表所有事件的原始交错顺序，完整顺序可在导出和原始证据中核对。

页面顶部显示“多项目自动归档 · 任务 05 · 关联执行证据”。首页选择项目后，从早到晚完整展示各会话；开始时间未知在后，相同或未知时间按来源实例和会话 ID 排列。页面每 1.5 秒检查已保存视图更新，并保留对话、执行过程与工具的展开状态；源采集独立于页面。旧快照也可按已有来源项目字段阅读，无需重新导入。

导出在原有字段之外增加 `session.tools` 和 `session.unsupportedItems`，不移除消息及原始证据。`tools` 使用当前正式接口的原子条目身份 `(来源实例, 会话, turnId, id)`，参数与结果同属该条目，不按文本或位置合并。`evidenceRef` 指向原始工具载荷，`order` 保留来源顺序；页面、公开查询和导出使用同一保存记录。`sourceStatus`、`sourceSuccess` 保留来源字段；展示 `status` 遇到错误／非零退出码为失败，声称完成但未取得结果为未知。`businessOutcome` 始终未知，不把执行完成当作业务成功。

支持正式接口中的 `commandExecution`、`mcpToolCall`、`dynamicToolCall`、`functionCallOutput`。独立函数输出没有请求身份时单独显示，不猜配请求。来源未保证完整性时显示未知；缺结果或来源结构化截断标记标为部分内容，正文中的截断提示仅报告是否截断未知。长输出不缩写；其他类型显示不支持并链接完整原始证据。来源没有独立返回的包装函数或嵌套调用不构造调用树，只按正式字段解析关系，不解析输出文字中的命令、句柄或子任务关系。

## 任务 05：关联执行证据（已验收完成）

会话内“关联会话”展示来源提供的子 agent、分叉及协作关系。身份来自 `parentThreadId`、`forkedFromId`、正式子 agent 来源字段、`subAgentActivity.agentThreadId` 或 `collabAgentToolCall`；活动关联不自动等于直接父子。已归档目标可进入自己的项目、消息与回合；缺身份、未归档、来源不可访问时明确说明。枚举已取得的关系元数据即使没有范围内正文也会保存为无正文的字段投影，经 `/relation-evidence/<id>` 核对；预览和旧正文仍不保存。查看和导出均只读本地保存，不连接来源或扩大首次范围。

每回合的“执行过程”增加“后台执行证据”，以来源实例、会话、回合、条目 ID 追踪命令保存修订。展示取得的 PTY 句柄、输出、退出码与每次原始证据；相同命令或复用句柄不合并。来源声称完成但没有退出码时仍为未知。当前历史协议没有独立轮询记录，句柄本身也不能证明后台运行；界面不伪造此类链路。修订只表示保存观察顺序，不代表执行因果。

根据用户 2026-10-26 的体验反馈，页面移除“结构化导出”和“选择导出范围”，日常使用以自动入库、直接阅读为主。关联会话在同一数据库内分别保存，是否入库遵守既有采集范围，不依赖页面或导出选择。

可选的 CLI／HTTP 结构化导出保留兼容性，默认单会话；显式使用 `export 会话ID --include-related --output 源码外路径` 或 `/export/<id>?related=1` 才包含一层已归档关联会话（父／子／分叉／交互）。导出 `related` 各自保留会话、修订与证据，`exportScope` 列明包含和未包含目标；不递归包含孙会话。没有包含所有者的关系证据引用为 null，`ownerEvidenceRef` 仍定位所有者自己的保存文档；包含后的 `evidenceRef` 指向整个导出文件。元数据投影经 `/metadata/<id>` 核对，明确区别于完整原始响应。

任务 05 于 2026-10-26 获用户明确“审核通过”，已登记完成，包含自动入库的页面调整。自行验证与真实来源边界见 [交验记录](docs/verification/05-execution-topology.md)。真实后台独立轮询、真实分叉正文及全部版本覆盖尚未认证。

## 当前边界

自动发现当前 `codexHome` 中正式接口可见的本机会话（含已归档会话及全部已知来源类型），依据来源 `projectId`，否则依据 `cwd` 分项目；均缺失时归入“项目未知”，身份还包含来源实例。不扫描其他应用或猜测其他 Codex 安装目录。枚举使用 `useStateDbOnly=true`，避免默认的来源元数据修复写入。列表附带的预览仅在请求内短暂存在，不保存为正文或原始证据。默认每轮完成后等 3 秒再次检查，可用 `--interval` 调整；每轮重新取得范围内回合及条目，不用最近更新时间作为完成条目的永久断点。旧会话只有来源更新时间进入范围才读取无正文回合元数据；没有可靠回合时间时显示错误。

自动读取只使用不含正文的回合元数据及限定回合的完整条目分页；手动导入仍核对完整回合和条目两种分页。分页冲突、格式不支持、读取或保存失败时保留上次成功快照，随后重试。保存成功才成为进度；同一目录只允许一个采集器。来源新快照缺少已保存的范围内条目时报告缺失并保留旧快照，不声称恢复成功。变化后的快照保留独立修订，完整导出的 `revisions` 包含旧会话视图、原始证据及文档内证据引用。没有新变化时不生成重复修订。

命令白名单仅含 `initialize`、`thread/list`、`thread/read`、`thread/turns/list`、`thread/items/list`，及握手通知。不会调用 `thread/resume`、`turn/start`、注入、历史命令或模型。新增 Python 组件不包含远端客户端；查看服务只绑定 `127.0.0.1`，没有外部脚本、字体或遥测。启动原生 App Server 时显式关闭 analytics、feedback 和 OTel 导出，并将子进程的 HTTP/HTTPS/ALL 代理覆盖为本进程保留、但不监听的本机端口，清空代理绕过列表，防止继承系统转发代理。当前版本已实测本机失败请求不影响历史读取；这是针对代理客户端的出口防护，并非系统防火墙，不能据此认证任意未来原生版本。

所有额外条目保留在原始证据中；子会话关系仅打开已授权保存的快照，不做全文搜索、标注、附件备份或受管理删除。`source.gaps` 和 `source.notDisplayedTypes` 明示限制。历史快照保存在本机数据库中；修订可从完整导出核对，尚未提供迁移或清理命令。当前真实工具样本只认证了命令与 MCP；动态工具与独立函数输出只有固定协议样本验证，不能据此认证真实来源覆盖率。详情见 [任务 02 验证边界](docs/verification/02-test-boundary.md) 和 [任务 03 交验记录](docs/verification/03-automatic-archive.md)。

## 开发验证

```powershell
python -m unittest discover -s tests -v
python -m mypy
```

应用运行不依赖 mypy。测试只替换外部 Codex 协议服务，经过真实导入、SQLite 保存、重开、HTTP 页面及 JSON 导出。真实数据不在测试或源码中。测试边界及样本定义见 [边界说明](docs/verification/01-test-boundary.md)。
