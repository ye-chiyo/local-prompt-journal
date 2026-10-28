# 整项目独立审查

日期：2026-10-28；审查者：full_project_audit 子 agent。

基准：origin/codex/remaining-log-issues；范围为当前工作树、相对默认分支的产品改动及既存数据保护高风险模块。未修改源码，未连接真实 Codex 历史，未重启正式服务，未提交或推送。

## 结论

产品代码未发现有证据支持的数据丢失、跨来源删除、来源写入、XSS 或分页遗漏问题。但发现以下 P2 发布验证工具回归，建议修复后再提交合并；当前不能宣称整项目无未处理发现。

## 发现

1. **P2：发布验证工具继续将会话目录当作消息正文。** `tools/verify_saved_session.py:115`、`tools/verify_tool_evidence.py:36` 请求 `/session/<id>` 并检查消息/工具 DOM；新版该路由是按需阅读目录。独立 3 消息 fixture 在文本、重启和来源证据均一致时仍 exit 1，`allMessageEvidenceLinksVisibleAndReadable=false`、`htmlHasPhaseLabels=false`。复现报告为本目录 `report.json`，预期清单为 `expected.json`。修复应遍历公开的回合目录/阅读链接，涵盖多页与工具独占回合，不改成跳过 DOM 检查。
2. **P2：消息摘录保留策略使验证器崩溃。** `tools/verify_saved_session.py:142-143` 无条件访问 `raw` / `sha256`；ADR 0002 的 dialogue-only 证据是 `sourceMessageExcerpt`，这些字段按设计已删除。对同一临时 fixture 经公开 `prune_tools` 后再次验证，exit 1 且 `KeyError: raw`；`dialogue-failure.txt` 记录 trace。修复应区分完整协议证据和消息摘录，核对实际来源对象、身份、文本、位置及可用原响应摘要，不应伪称摘录仍有完整原始响应校验。工具专用验证器应明确识别不适用的 retention 模式。

## 覆盖与独立证据

- 读取 AGENTS、PRODUCT、DESIGN、GLOSSARY、3 个 ADR、当前分页/项目删除/页面精简规格。
- 审查来源只读方法白名单、DB-only 枚举、分页冲突/游标和身份核对、enabledAt 与采集恢复边界；桌面主进程识别和监视器停启路径。
- 审查 SQLite 保存事务、缺失条目拒绝、版本投影、空回合过滤、6 会话分页、30 回合按需继续、固定版本来源和正文惰性读取。
- 审查受管理删除/排除事务、迟到采集保护、共享附件引用保留、附件清理重试、项目删除确认集合签名及跨来源身份。
- 审查附件路径边界、远端不下载、校验字节、丢失状态、导出一层范围及离线包。
- 审查 Web loopback/Host/Origin/CSRF、内容转义/CSP、附件 inert 类型、正文请求竞态/取消/重试/自动刷新保护、精简与 reduced-motion。
- 审查本地插件 6 项只读工具、分页参数、正文分段、构建和只读 DB；扫描 Git 跟踪文件和变更中的敏感字段。
- 独立执行 `python -m unittest discover -q`：72 项通过，42.482 秒。没有以自动检查代替真实用户验收。
- Git 跟踪的数据库、日志、归档包、位图扫描仅命中 `.scratch/ui-polish/reference/approved-desktop.png`。已实际查看：该图为产品功能讨论等示例数据的设计参考，没有真实用户会话、本机路径或账户凭据。未发现硬编码密钥。排除未跟踪 .impeccable/ 与 .playwright-cli/ 是根 agent 的交付职责。

## 未实测的边界

- 本轮未再次执行实际桌面应用关闭/重启、登录任务安装、正式库迁移或正式 8766 更新，以避免打断用户和修改正式数据。
- 未重新执行全浏览器视觉验收；现有体验/截图记录由根 agent 提供，本审查未将其冒称本轮独立浏览器结果。
- 未针对所有 Windows 版本、异常磁盘/权限、海量实时数据、外部 Codex 新版本协议和所有第三方附件类型做穷举；原有明确缺失/不支持语义仍适用。
- GitHub 权限、分支保护、PR 合并和最终远端提交一致性由根 agent 在交付操作中核对。


## 修复后的最终复核

根 agent 已修正两个验证工具及嵌套 details 解析，新增公开 CLI 回归用例。本子 agent 阅读修复后源码，并用发现问题时的原始独立预期清单重新运行：

- `recheck-full.json`：完整协议样本 exit 0，6 个 raw 证据，文本/阶段、进程重启、原始消息对象、证据链接、哈希和实际载荷全部通过。
- `recheck-excerpt.json`：对话摘录样本 exit 0，6 个 sourceMessageExcerpt，原始消息对象、阶段、正文、证据链接均通过；不适用的 raw 哈希/载荷校验返回 null，没有宣称仍保有完整协议。
- `negative-recheck.json`：在独立预期清单中故意把最终回答 phase 改错，验证器 exit 1，文本/阶段及原始消息对象检查明确失败，证明没有以删除验证来消除发现。
- 阅读 `verify_tool_evidence.py` 修复：逐回合正文检查保留，工具按策略移除时记录缺失并失败，而不是访问空对象崩溃。根 agent 已运行新增的两项 CLI 集成测试；本子 agent 不冒称这是自己的额外独立测试。

**最终结论：本审查发现的两项 P2 均已修复并复核；当前没有未处理的可复现阻碍项，可以继续用户已授权的 commit、合并与推送。上述未实测范围仍适用；此结论不表示正式服务已经发布，也不替代 GitHub 最终远端一致性核对。**


## 根 agent 最终交付验证

修复后全套 `python -X utf8 -m unittest discover -q`：74 项通过，45.093 秒。`python -m mypy`：18 个生产文件通过；`git diff --check` 通过。新增 CLI 回归通过完整协议、消息摘录、错误清单和已移除工具的正反向验证。

用户已明确授权审查通过后 commit、合并和推送。本记录随唯一新增实现 commit 提交；通过 PR 合并到 GitHub 实际默认分支 `codex/remaining-log-issues`，保留既有历史。GitHub 操作的实际提交号与 PR 链接在交付回复中核对，不预先登记尚未执行的操作。

待提交文件已在源码外逐文件 SHA-256 备份；排除 `.impeccable/`、`.playwright-cli/`。正式 8766 未重启，正式数据库、源日志、附件及采集启用时间未改写。本次不等同于新的人工浏览器验收或正式服务发布。
