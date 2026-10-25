# 本机 Codex 会话记录

任务 01 的最小本机应用：明确选择一个 Codex 桌面会话，通过同版本 App Server 的只读历史接口导入，保存用户提示与 AI 消息，在时间线中回看，并导出含原始证据的 JSON。

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

## 当前边界

只支持手动导入一个明确指定的会话和查看已保存快照。当前适配器要求正式接口支持完整回合及条目分页；不支持时明确失败，不自动恢复会话，不静默回退旧日志。源变化导致两种分页结果不一致时，拒绝发布新快照，保留上次成功保存的版本。

命令白名单仅含 `initialize`、`thread/read`、`thread/turns/list`、`thread/items/list`，及握手通知。不会调用 `thread/resume`、`turn/start`、注入、历史命令或模型。新增 Python 组件不包含远端客户端；查看服务只绑定 `127.0.0.1`，没有外部脚本、字体或遥测。启动原生 App Server 时显式关闭 analytics、feedback 和 OTel 导出；其版本行为仍由真实契约检查约束。

所有额外条目保留在原始证据中；任务 01 不解析工具关联，不浏览子会话，不做全文搜索、标注、附件备份、自动同步或受管理删除。`source.gaps` 和 `source.notDisplayedTypes` 明示这些限制。历史快照保存在本机数据库中；尚未提供快照历史浏览、迁移或清理命令。

## 开发验证

```powershell
python -m unittest discover -s tests -v
python -m mypy
```

应用运行不依赖 mypy。测试只替换外部 Codex 协议服务，经过真实导入、SQLite 保存、重开、HTTP 页面及 JSON 导出。真实数据不在测试或源码中。测试边界及样本定义见 [边界说明](docs/verification/01-test-boundary.md)。
