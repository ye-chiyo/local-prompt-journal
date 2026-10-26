# 任务 10：受管理删除与删除排除

日期：2026-10-26（Asia/Shanghai）。实施基线 `c90e8d249dda8b4c5be5435ee8f5ea00748939f2`；独立分支 `codex/issue10-managed-deletion`，基于集成分支 `codex/remaining-log-issues`。本记录保留技术交验及验收前过程；用户于 2026-10-26 明确验收并要求提交，最新登记见文末。

沿用规格及任务 01 已确认的整体公开边界：应用公开 Python／CLI／HTTP → 真实 SQLite、受管理附件、重开、自动采集及导出。只替换最外部 Codex 协议服务；文件清理故障仅在文件系统边界注入。测试不查询内部 SQLite 表，不复制私人日志，不删除正式数据。

## 实现行为

`Journal.delete_session(id, instance=None)` 原子删除指定来源会话的所有快照并持久保存排除。`exclusions()` 返回 `deleted` 或 `cleanupPending`、来源身份、删除时间及实际错误；`restore_session()` 只解除排除，不立即读取来源，不改变原 `enabledAt`。多来源同 ID 必须指定来源。

删除会移除已删除所有者的关系元数据投影及采集状态条目；其他会话实际保存的关系、正文和原始证据原样保留，其目标状态显示 deleted，不能打开已删除正文。保存和删除使用 SQLite `BEGIN IMMEDIATE` 跨线程／进程串行化附件取得、快照持久化和无引用附件清理；采集器读取正文前检查排除，保存时再次检查，读取途中的删除不会被迟到快照覆盖。

附件清理按全部保留历史版本的实际引用判断共享关系。无引用副本清理失败后，正文和证据已移除，排除与待清理摘要仍持久保存；界面显示未完成，不允许提前恢复。管理页可重试，应用重开也会重试。数据库事务失败则不宣称完成。这里的删除是应用可访问数据的清理，不宣称取证级磁盘擦除，不删除 Codex 来源、原附件或用户另存导出。

会话页提供“删除此会话的受管理日志”，先进入确认页明确范围，再 POST 执行。全站顶部可进入 `/manage/exclusions` 查看状态、重试及显式解除排除；GET 不修改数据。POST 校验回环 Host、同源 Origin 与服务实例随机 token，操作后 303 回管理页，避免刷新重放。原查询、证据、导出和附件地址在删除后返回未保存。

CLI：`delete 会话ID --yes [--source-instance 来源实例]`、`restore 会话ID [--source-instance 来源实例]`、`exclusions`。删除清理未完成时 CLI 输出 pending 状态并返回退出码 1。

## 红绿与验证

第一片先运行全部修订删除／共享附件保留的公开链路，初始缺少 `delete_session` 失败，再实现最小持久删除和引用清理，通过。第二片实际运行自动采集，发现删除后仍读取目标、在来源故障时显示目标错误；在采集正文前检查排除并过滤持久状态后通过。相同 ID 跨来源及读取途中删除场景、文件占用失败／重开重试场景随后验证了同一公开边界。HTTP／CLI 片初始缺少页面删除入口失败，增加确认页、token、管理页及 CLI 后通过。

5 项必要公开行为检查位于 `tests/test_deletion.py`：

- 全部历史／证据／搜索不可访问；其他会话证据不变；共享图片保留而独占附件清理；源文件保留。
- 自动采集持续运行及重启后不重新归档；来源目标故障时不读取正文；显式恢复沿用启用时间，启用前正文仍禁止读取。
- 相同会话 ID 的不同来源互不影响；另一 Journal 实例不能保存删除前已取得的迟到 capture。
- 文件系统拒绝清理时持久 pending，阻止提前恢复；重开不误报完成，解除占用后重开完成清理。
- HTTP 确认页只读、无效／缺失 token 拒绝、删除后证据 404；CLI 显式恢复不立即重建数据，再次导入及 CLI 删除正常。

完整 30 项 `python -m unittest discover -s tests -v` 通过，耗时 17.996 秒；`python -m mypy` 12 个生产文件通过。随后仅调整 POST 为 303 跳转及管理页结果提示，复用该 HTTP／CLI 检查通过（1.334 秒）；最终再次执行类型检查及 diff 检查。真实浏览器操作由集成后的任务 11 补充记录，不把 HTTP 字符串检查记作浏览器验收。

## 交付状态（验收前记录）

未操作正式日志数据库、正式服务、采集启用时间或既有任务 09 worktree。任务 10 的技术项已验证，Execution 为 `implemented-awaiting-user-acceptance`，Status triage 仍为 ready-for-agent；尚无用户明确通过记录。

项目此前用户确认“体验确认后再提交并登记完成”，本轮保留该门槛：实现分支不创建临时 commit，以源码外 binary patch 与新文件副本交给集成分支；这取代 implement-spec 通常的实现提交／merge commit 步骤。未 push。

## 集成浏览器发现及修复

任务 11 的真实 IAB 页面表单操作确定性返回 403。父代理按 diagnosing-bugs 先复现、列出假设，再只采集窄请求头，证据在源码外 `D:\AI\journal-release-evidence-20261026\browser-post-headers.jsonl`：正确回环 Host，`Origin: null`、`Sec-Fetch-Site: same-origin`、正确表单 Content-Type，无 Referer。未采集正文、随机 token 或私人日志。

问题是应用内沙箱页面的合法同源表单携带 opaque Origin，而原处理只接受缺省或 HTTP Origin。先扩展原有 HTTP／CLI 用例，以真实头部提交合法 token，实际返回 `403 != 303`（0.730 秒），形成公开 HTTP 边界的回归红灯。修复仅对 POST 增加 `Origin: null` 且 `Sec-Fetch-Site: same-origin` 的允许条件；回环 Host、随机 token 继续检查，GET 的 Origin 规则不变。同一测试同时确认有效 token 但 null+cross-site、显式外站 Origin 均为 403，不创建重复测试。

另将 CLI serve 帮助改为“不采集的本机阅读与管理服务”，准确反映新增管理操作。未增加调试日志；最终真实浏览器回验仍由父代理执行后记录，此处不提前声明通过。

## 最终集成浏览器复核

父代理已在最终无敏感演示 `final-browser-demo/data` 的真实 IAB 页面实际提交 B 的删除确认表单成功，截图 `D:\AI\journal-release-evidence-20261026\browser-deletion-complete.jpg`。`browser-deletion-api-report.json` 交叉核对：受控来源仍有四会话，持续对账后本地仅 A/C/D；B 搜索为 0，正文、原始证据、JSON 导出及离线包均为 HTTP 404。

父代理随后实际点击“解除删除排除”，采集器自动带回 B，最终 A/B/C/D 四会话、无排除、原 `enabledAt=190` 不变，截图 `browser-restore-complete.jpg`。进程重启后重新打开及最终中文搜索、命中定位、证据和工具展开均由 `browser-final-report.json` 记录。这里只操作独立演示数据，不触及正式日志；该报告 userAccepted:false 仍保留，技术浏览器验证不等于用户验收。

## 2026-10-26 用户验收与提交

用户在首页布局调整及功能说明后明确回复：“我已经通过检验请进行commit”。据此登记任务 10、11 本轮验收完成，随 codex/remaining-log-issues 将实现、检查、交验文档和首页布局调整提交一次，不自动 push、不合并 master。上文“尚未验收／等待确认／未提交”的描述保留为验收前过程记录，以本节和任务文件顶部 Execution 为最新状态。

本次用户确认不扩大技术验证范围：任务 11 的严格性能条目仍未勾选，真实来源状态差异及尚未认证项目原样保留；源码外原报告中的 userAccepted:false 等采集时字段不回写。正式日志数据、采集启用时间及既有任务 09 工作区不作改动。
