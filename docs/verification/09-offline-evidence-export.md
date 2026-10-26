# 任务 09：附件归档与离线会话包

日期：2026-10-26（Asia/Shanghai）。用户在搜索体验反馈修正后明确回复“我已经审核通过请你提交commit”。任务 09 已登记 Execution: completed，实现、必要测试与交付记录按约定一次提交。下文等待确认及未提交等文字保留为验收前过程记录，当前状态以本段和文末为准；真实来源验证边界不因用户验收而扩大。

基线：`b5f7818c5e8e0a4c5a012dc38388ab7a38917e04`。源仓库 master 有任务 07 的未提交修改，仅作只读核对。任务 09 工作区为 `C:\Users\614\.codex\worktrees\task09-offline-evidence\日志项目`，分支 `codex/task09-offline-evidence`。独立验证目录 `C:\Users\614\AppData\Local\LocalPromptJournal\task09-acceptance`；检查监听端口后选 8789，不占用正式及任务 07 服务。

## 实现前固定事实与公开边界

既有已确认边界：外部 Codex 协议进程 → Collector 自动保存／公开导入 → 真实文件与 SQLite → HTTP、浏览器与可选导出。只替换外部协议进程，不检查私有方法、表结构、文件数量或去重算法。TDD 沿用此已授权边界，不重新询问。

独立事实在生产实现前定义于 `tests/fixtures/attachment_facts.py`：PNG 是固定 base64 原始字节；普通附件是固定含 CRLF、NUL 和 0xff 的字节，另一个同名附件是不同的固定字节。main/turn/picture 与 shared 共用一张图片；documents 的两条正式 MCP resource_link 各自指向不同内容；missing 的本机路径不存在，远端引用 example.invalid 不访问。empty 无附件。child 共享图片且 parentThreadId=main；grandchild 的 parentThreadId=child；main 指向 unarchived，正文未归档。默认包只有 main，显式一层为 main、child，无 grandchild 或 unarchived 正文。预期不从产品查询或打包算法生成。

原文件移动只操作本任务受控样本。预期字节及 SHA-256 在归档前另用 PowerShell Get-FileHash 固定。移动导出包到不同目录后以标准 zipfile/json 与独立清单核对，直接打开原字节文件，不依赖日志服务、数据库、原路径或远端。

## 来源能力与最小方案

本机 `codex app-server generate-json-schema --experimental` 的正式 UserInput 提供 localImage.path、localAudio.path、image.url/fileId、audio.url、mention.path；工具 imageView.path，imageGeneration.result/fileId/savedPath；dynamicToolCall.contentItems 有 inputImage.imageUrl、inputAudio.audioUrl。MCP result.content 为开放内容数组，只识别明确的 image/audio data、resource blob、resource_link uri。文本、普通 Markdown URL、命令参数／输出中的路径不猜附件；skill 不是附件。fileId 无当前白名单内本机解析接口时列未取得，不猜附件存储路径。

将明确附件原字节存入源码外 data-dir 的受管理目录，快照中保存关系、引用、实际字节数及 SHA-256。老快照只展示其已有证据中的引用和未归档说明，不用当前原文件冒充历史。离线包是可选 ZIP；沿用既有结构化导出并附文件和缺失清单，默认单会话，一层范围复用任务 05，不连接来源。不实现任务 07、08、10、11。

## 实际验证结果

- 两项新增公开场景保护自动归档／HTTP／原路径失效／重开，以及移动包的原字节／修订／一层范围；没有内部结构、物理去重数量或私有调用断言。现有页面检查仅将已经过时的“附件尚未备份”更新为“附件未取得”。最终完整 25 项检查通过（14.037 秒），mypy 11 个生产文件通过，`git diff --check` 通过。
- 独立受控协议经 Collector 自动取得 4 个会话，无需手动逐条下载。main 当前有 5 个已归档附件引用（两条共享图片、两份同名不同字节普通附件、来源内嵌生成图片）及 2 个缺失引用（不存在文件、远端 URL）。empty 无附件仍正常保存。child 保留自己的共享图片关系；所有消息、工具、来源身份分别保留。
- 初次归档前先以 PowerShell `Get-FileHash` 固定 68 字节 PNG、54 字节普通附件和 34 字节同名附件的 SHA-256，保存于源码外 `final/hashes-before-archive.json`；独立原始字节及会话范围见 `final/expected-before-archive.json`。随后在来源更新前先保存 `final/update-before-archive.json`，将普通附件更新为固定 20 字节 `New revision bytes.\n`，增加内嵌 PNG 与失效 savedPath 同时存在的生成图片。已归档修订分别保留 54 与 20 字节，不把当前文件替换进旧版本。
- 只移动本任务创建的 sample.png、sample.bin；再以不同分页公开导入并重开，保存副本仍可取得。任务 09 查看服务随后正常关闭并以新进程重启，继续使用同一独立数据库，不重新导入恢复。正式服务及任务 07 未停止或迁移。
- 真实 Chromium 浏览器在最新 8789 页面核对任务 09 标题与独立数据库路径，从消息实际点击 PNG，原文件移动及重启后仍解码成功（naturalWidth/Height 均为 1）。展开执行过程及工具后实际下载普通附件，文件逐字节等于事前发布的 20 字节。缺失卡片的本机不存在／远端未下载两种说明可见，实际点击附件原始证据并核对 main/turn/picture、shared、documents、missing 的来源载荷。缺失说明截图 `missing-attachments.png` 已视觉查看，无遮挡。保存图片卡片的一次元素截图因等待稳定超时，未计为通过；附件实际打开、解码及字节核对已独立通过。
- 使用公开 CLI `bundle main` 与 `--include-related` 导出 ZIP，再将包复制并解压至另一个目录 `final/offline-moved/main` 和 `final/offline-moved/related`。独立脚本仅使用 Python 标准库，不导入产品、不读取 SQLite、不连接服务，并禁用 socket。两个目录分别包含 main，以及 main+child；孙会话 grandchild 列为 beyondOneHop，unarchived 列为 notArchived，均没有正文或附件混入。默认包 20 条跨修订附件关系及 16 条原始证据核对通过；关联包 22 条关系及 22 条原始证据核对通过。每包的全部实际文件与归档前字节／PowerShell 校验和独立更新事实一致，校验原始响应 raw 的 SHA-256 与解码 JSON，缺失条目明确。报告 `final/offline-report.json` 保留 userAccepted:false。

## 双轴审查

code-review 两个独立子 agent 均从开工基线检查全部未提交差异及新增文件，不只检查 HEAD，不创建临时 commit。

Standards 初审 P2：原附件关系断言两侧均取产品输出，独立预期不足。已在现有场景逐项对照实施前固定引用、itemId、main/turn；不新增测试数量。复核：明确规范违反 0，需处理 smell 0。

Spec 初审 P1：原路径失效后复用副本连旧 evidenceRef 一起恢复，分页变化可能错位。仅继承经过验证副本的字节身份、名称和取得信息，保留本次来源关联及证据位置；原自动场景使用分页 1 → 移动原文件 → 分页 20，按固定原路径复测。初审 P2：失效生成图片 savedPath 遮蔽有效内嵌 result。已优先有效非空来源 result；外部协议实际提供此组合，保存及移动包原字节通过。复核另核对空 result+fileId 仍明确未取得。Spec 复核未解决发现 0。

## 来源与集成边界

本机正式 schema 已生成在独立 schema/，当前授权旧证据 `02-raw-before-implementation.json` 仅有 text 用户输入，没有 imageView/imageGeneration 或真实用户附件；不扫描其他私人会话，不重新读取启用前正文。真实输入附件、MCP resource_link／blob、生成图片等的实际桌面端到端字节兼容性尚未认证。受控协议通过不能替代真实认证。若后续需要补真实样本，最小正常操作是用户在本项目一个新回合发送一张无敏感图片或正式文件附件，再单独授权核对该新回合；本次不为等待样本扩大采集范围。

本机路径无来源当时校验时，记录取得时间及 localFileAtArchiveTime，页面提示副本是归档时读取的字节，不能证明消息发生时版本。来源提供原字节或明确 SHA-256 时保存／核对对应内容。历史未归档附件只列说明，不静默读取今天文件冒充历史。包与页面均不宣称完整原生备份。

初检源仓库 master 修改为 app.py、topology.py、web.py，新增 07-feedback-corrections.md、human.py、feedback_facts.py、test_feedback.py。最终只读核对源 HEAD 仍为基线，另见 README.md、tools/verify_saved_session.py 正在被修改，未触碰或追随这些未提交变化。任务 09 不包含任务 07 人工功能，未合并主线或任务 07，未验证组合版本。任务 08、10、11 未开始；所有其他任务文件和状态未修改。

## 交验位置与运行

服务：`http://127.0.0.1:8789/session/main`；无附件：`/session/empty`；共享引用子会话：`/session/child`。当前为只读体验服务，受控自动采集验证已完成并停止，只使用任务 09 保存数据。页面明确展示此进程未运行采集器。1970 年时间均为受控事实。

Windows 包环境解析后的实际数据根目录为 `C:\Users\614\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\LocalPromptJournal\task09-acceptance`，与上述 LocalAppData 路径指向同一受控目录。`final/data/journal.sqlite3` 和 final/data/attachments 为任务 09 数据；`final/exports/main.zip`、`final/exports/related.zip` 为实际导出；`final/offline-moved/main`、`final/offline-moved/related` 是已经移动、解压并独立验证的目录，内有 session.json、manifest.json、README.txt 与 attachments/。

本次服务用源码外 preview.py 的专用停止标记正常重启，不终止其他服务。若当前任务 09 服务已经停止，可从实际工作区启动：

```powershell
Set-Location -LiteralPath 'C:\Users\614\.codex\worktrees\task09-offline-evidence\日志项目'
python -m prompt_journal --data-dir 'C:\Users\614\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\LocalPromptJournal\task09-acceptance\final\data' serve --port 8789
```

代码分支 `codex/task09-offline-evidence`，HEAD 仍为基线；任务 09 issue 保留原 Status 及未勾选验收项，无 Execution: completed。等待用户明确表示通过／可以提交后，才按要求登记本任务并创建一次 commit，不 push、不合并、不开始后续任务。


## 受控图片样本校正与最终数据

独立解码发现最初固定的 68 字节 PNG 有 IDAT CRC 错误；浏览器虽然显示 naturalWidth=1，不能把宽高读取当作所有解码器兼容证明。归档字节本身一致，不是产品重新编码造成。仅校正受控 fixture 的 PNG CRC，不改生产实现，不改旧保存历史。校正后的原文件在归档前用独立解码器实际打开，并在新的 `final/` 目录重新固定原始字节和 PowerShell SHA-256。随后重新执行 Collector 自动保存、来源修订、原文件移动、不同分页同步、CLI 两种包、移动解压和禁用 socket 的独立核对，上述 20/22 条关系及 16/22 条原始证据结果再次通过；相关两项公开检查再次通过（1.292 秒）。旧尝试材料留在 final/ 外，不用它作为最终图片认证。

最终 8789 服务连接 `final/data/journal.sqlite3`，最终交付包与解压材料全部位于 `final/` 下。浏览器自动化工具禁止 file: 协议，故不宣称浏览器离线文件导航通过；离线结构化记录、文件字节及校验通过不导入产品的独立进程实际打开核对，图片另使用本机独立解码器查看。没有为此开放额外服务或修改整机网络。

最后将本任务 preview 服务正常关闭，从实际 worktree 用文中正式 `serve --port 8789` 命令启动最新版本。浏览器重新加载校正后的已保存 PNG，原路径仍已移动，解码成功；最终页面数据库路径为 final/data。公开 HTTP `/bundle/main` 与 `/bundle/main?related=1` 实际返回 application/zip，标准 zipfile/json 读取的格式版本均为 1，包含范围分别为 main 与 main+child。规范及规格针对图片 fixture 和交验文档的增量复核均无未解决问题，校正后的 PNG 三个 chunk CRC 亦由独立审查核对有效。未创建任何 commit。

## 2026-10-26 用户体验反馈：简化搜索与明确无结果

用户询问搜索是否可用，并要求未命中时明确提示、删除搜索表单下两段技术说明。当前任务 09 演示样本没有“雨巷纸伞”，此前实际为无命中，长说明遮蔽了反馈。此次仅移除被点名的范围／匹配说明，将无结果显示为“未找到相关内容”，说明当前范围未匹配查询词并建议换词或扩大范围；空输入显示“请输入搜索关键词”。查询词按纯文本转义；不改变搜索、范围或来源行为。

复用现有搜索及 HTTP 页面 4 项检查通过，未新增测试；mypy 11 个生产文件、git diff --check 通过，界面检测无报告。核对 8789 原进程命令行确为任务 09 final/data 后，只重启此查看服务。真实浏览器在 1091×918 查看“雨巷纸伞”的清楚无结果状态，两段说明已不在页面；实际输入“受控图片”并点击搜索返回已知 picture 消息 1 条。390 像素宽的页面 DOM 检查无横向溢出。两次截图捕获超时，未记作截图视觉验收；浏览器实际操作、结果与 DOM 核对分别记录。规范及规格增量复核均无未解决发现。

仍等待用户体验确认，不登记任务完成，不创建 commit，不修改其他任务状态。

## 用户验收

2026-10-26（Asia/Shanghai），用户明确回复：**“我已经审核通过请你提交commit”**。按既定门槛登记任务 09 完成、勾选验收项，保留 ready-for-agent 的 triage 含义；将本任务实现、两项公开行为测试、既有页面检查的必要更新、搜索反馈修正及交付记录合并为一次 commit。没有创建实现、修复或审查临时提交。

规范与规格最终审查均无未解决问题；既有独立清单和运行报告保留其原始 userAccepted:false 等历史字段，不追改验证证据。真实桌面附件端到端兼容性仍未认证，任务 07 人工功能未集成，未验证组合版本。任务 09 只在 codex/task09-offline-evidence 分支完成，不修改其他任务状态或依赖，不推送、不合并 master、不开始任务 08、10、11。

提交前对最终版本复核：完整 25 项公开行为检查通过（14.458 秒），mypy 11 个生产文件通过，git diff --check 通过。运行材料、受控数据库、附件和导出包均保留在源码外，不纳入提交。
