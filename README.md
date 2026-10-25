# 本机 Codex 会话记录

最小本机应用：明确选择一个 Codex 桌面会话，通过同版本 App Server 的只读历史接口导入，保存用户提示、AI 消息及来源实际返回的工具证据，在时间线中回看，并导出含原始证据的 JSON。任务 02 的工具证据功能及分组阅读已于 2026-10-25 通过用户验收。

规划更新（2026-10-25）：用户已确认后续改为自动发现和持续归档，不再要求日常手动同步；不同项目分别记录，同一项目按会话开始时间完整排列，不交错消息。原任务 03、04 合并为[多项目自动归档与持续同步](.scratch/local-prompt-journal/issues/03-capture-scope.md)，见[决策记录](docs/adr/0001-automatic-project-archive.md)。该功能尚未实现，下列命令及“当前边界”描述的仍是已交付版本；Windows 登录自启动与首次旧历史回补范围尚待确认。

运行环境：Windows、Python 3.12+、桌面捆绑的 `codex.exe` 位于 PATH。应用只使用 Python 标准库；不需要 API key、模型服务、npm 安装或远端数据库。真实验收版本及限制见 [验证记录](docs/verification/01-single-session-proof.md)。

## 使用

在本目录的 PowerShell 运行：

```powershell
# 先检查用户选择的无敏感会话；不会恢复或执行历史任务。
python -m prompt_journal probe 会话ID

# 导入指定会话。重复导入会保留快照版本，当前时间线不会重复显示消息。
python -m prompt_journal import 会话ID

# 开启只读页面，浏览 http://127.0.0.1:8765 。Ctrl+C 关闭。
python -m prompt_journal serve

# 关闭应用后仍可查询、导出；这些命令不会连接 Codex。
python -m prompt_journal list
python -m prompt_journal show 会话ID
python -m prompt_journal export 会话ID --output C:/Users/614/AppData/Local/LocalPromptJournal/exports/session.json
```

默认数据目录：`%LOCALAPPDATA%/LocalPromptJournal/data/`，数据库为 `journal.sqlite3`。用 `python -m prompt_journal --data-dir 外部目录 ...` 更改。数据库与导出均拒绝写入本项目源码目录；Git 同时忽略 SQLite、JSONL、缓存与运行时产物。

`probe` 无预期清单时只做能力探测并返回退出码 1，表示尚未验收；不会将“能够连接”误报为“样本通过”。薄真实契约检查需提供**事先独立定义**的完整样本清单：

```powershell
python -m prompt_journal probe 会话ID --page-size 1 --expected C:/Users/614/AppData/Local/LocalPromptJournal/acceptance/expected-desktop-sample.json --report C:/Users/614/AppData/Local/LocalPromptJournal/acceptance/real-contract.json
```

真实清单包含 `definedBeforeImport: true`、`thread.id`、`page.hasMore: false`，及 `turns[].id/status/messages[]`。消息使用实际桌面 `userMessage` / `agentMessage` 的身份、文本与阶段；不能从本应用输出反向生成验收预期。

## 查询与证据

- Python 公开接口：`Journal.import_session`、`session`、`sessions`、`export_session`；`CodexHistory` 是最外部 Codex 数据源边界。
- HTTP：`GET /api/sessions`、`GET /api/session/<id>`、`GET /session/<id>`、`GET /export/<id>`、`GET /evidence/<id>/<index>`。
- 相同会话 ID 来自多个来源实例时，查询须指定 `?source=<instance>`，CLI 使用 `--source-instance`，防止合并不同来源。页面链接自动携带身份。
- 导出是一个自包含 UTF-8 JSON，含 `schemaVersion`、`session`、`evidence`。每条消息的 `evidenceRef` 是该文件内的 JSON Pointer；`evidence` 保存请求参数、实际响应、原始解码行、SHA-256 与采集时间。`raw` 为 UTF-8 解码后的接口行，换行遵循 Python 文本流规范，并非原生数据库的逐字节备份。
- 保留原始消息 ID、回合 ID、来源实例、源时间、状态与消息顺序。未知时间／阶段显示未知；附件未备份，非文本消息标记部分内容。AI 原文按纯文本显示，不执行 HTML、命令、工具或附件。

每回合默认连续展示用户、AI 过程及最终消息，保留对话原文与彼此的来源顺序。工具和其他非对话条目集中在回合末默认折叠的“执行过程”中，组内按来源顺序排列；展开后仍可点击“工具执行”查看参数、全部已取得结果、错误、状态及原始证据。工具读取的技能或配置文档正文保留在对应结果里；用户粘贴的文档、AI 对技能的解释仍直接展示，不按关键词隐藏。分组后的页面位置不代表所有事件的原始交错顺序，完整顺序可在导出和原始证据中核对。

页面顶部显示“任务 02 工具证据 · 分组阅读”及工具条数，用于识别新版本。本次阅读调整直接使用已保存快照，不需要重新导入；任务 01 时尚无工具视图的旧快照仍需手动导入以取得工具记录。

导出在原有字段之外增加 `session.tools` 和 `session.unsupportedItems`，不移除消息及原始证据。`tools` 使用当前正式接口的原子条目身份 `(来源实例, 会话, turnId, id)`，参数与结果同属该条目，不按文本或位置合并。`evidenceRef` 指向原始工具载荷，`order` 保留来源顺序；页面、公开查询和导出使用同一保存记录。`sourceStatus`、`sourceSuccess` 保留来源字段；展示 `status` 遇到错误／非零退出码为失败，声称完成但未取得结果为未知。`businessOutcome` 始终未知，不把执行完成当作业务成功。

支持正式接口中的 `commandExecution`、`mcpToolCall`、`dynamicToolCall`、`functionCallOutput`。独立函数输出没有请求身份时单独显示，不猜配请求。来源未保证完整性时显示未知；缺结果或来源结构化截断标记标为部分内容，正文中的截断提示仅报告是否截断未知。长输出不缩写；其他类型显示不支持并链接完整原始证据。来源没有独立返回的包装函数或嵌套调用不构造调用树，不解析输出中的命令、句柄或子任务关系。

## 当前边界

只支持手动导入一个明确指定的会话和查看已保存快照。当前适配器要求正式接口支持完整回合及条目分页；不支持时明确失败，不自动恢复会话，不静默回退旧日志。源变化导致两种分页结果不一致时，拒绝发布新快照，保留上次成功保存的版本。

命令白名单仅含 `initialize`、`thread/read`、`thread/turns/list`、`thread/items/list`，及握手通知。不会调用 `thread/resume`、`turn/start`、注入、历史命令或模型。新增 Python 组件不包含远端客户端；查看服务只绑定 `127.0.0.1`，没有外部脚本、字体或遥测。启动原生 App Server 时显式关闭 analytics、feedback 和 OTel 导出，并将子进程的 HTTP/HTTPS/ALL 代理覆盖为本进程保留、但不监听的本机端口，清空代理绕过列表，防止继承系统转发代理。当前版本已实测本机失败请求不影响历史读取；这是针对代理客户端的出口防护，并非系统防火墙，不能据此认证任意未来原生版本。

所有额外条目保留在原始证据中；不浏览子会话，不做全文搜索、标注、附件备份、自动同步或受管理删除。`source.gaps` 和 `source.notDisplayedTypes` 明示这些限制。历史快照保存在本机数据库中；尚未提供快照历史浏览、迁移或清理命令。当前真实样本只认证了命令与 MCP；动态工具与独立函数输出只有固定协议样本验证，不能据此认证真实来源覆盖率。详情见 [任务 02 验证边界](docs/verification/02-test-boundary.md)。

## 开发验证

```powershell
python -m unittest discover -s tests -v
python -m mypy
```

应用运行不依赖 mypy。测试只替换外部 Codex 协议服务，经过真实导入、SQLite 保存、重开、HTTP 页面及 JSON 导出。真实数据不在测试或源码中。测试边界及样本定义见 [边界说明](docs/verification/01-test-boundary.md)。
