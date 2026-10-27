# 压缩后从这里继续

2026-10-27（Asia/Shanghai），用户要求“准备一次压缩对话”。本文件用于接续同一个任务，不是完成交付。

## 当前目标与用户授权

对本机会话记录进行 PC 页面重新设计，已选定 **B · 通透内容台**。用户明确回复两次：

1. “B · 通透内容台，同意实施”。
2. 实施计划问题回复“审核通过”。

**两项审核均已通过，不再问用户选方案或重复审核计划。** 继续完成实现、验证，再更新正式 8766 供用户体验。主要适配 PC，不要求手机适配。此前用户嫌旧版及第一轮 refinement 单调，因此必须对齐 B 图，不要回到旧样式的小修小补。

主路径：项目列表 → 按会话分组的分页回合目录 → 独立单回合阅读；以及中文搜索。辅助页采集状态与删除管理共享样式。ID、证据位置、保存版本等默认收进“来源信息”，正文、角色、时间、附件突出。

不改变数据库、采集策略、来源身份、保存版本、附件字节、原文和路由契约；目录不预读正文，单回合只加载所选回合。消息保持纯文本转义，不执行 HTML／代码，不恢复已清理工具板块。来源起始时间、分页、搜索高亮、懒加载及上一／下一／返回均须保留。

## 仓库与既有发布

- cwd `D:\AI\日志项目`，PowerShell，Python `D:\python\python.exe`。
- 当前分支 `codex/ui-polish`，HEAD `e30ec879bfa435e72a34d607590d0f5c0012fbf8`。
- HEAD 是上一轮已验收的目录／压缩／只保留对话实现，已推送到私有 GitHub `https://github.com/ye-chiyo/local-prompt-journal` 的 `codex/remaining-log-issues`。新美化分支尚未提交／推送。
- 本轮体验验收前不自动 commit／push，不创建 PR。
- AGENTS.md：任务在 `.scratch`，读取 `docs/agents/issue-tracker.md`、`triage-labels.md`；领域读 GLOSSARY.md、docs/adr/。ADR 0001 自动归档与顺序，0002 正式库只保留对话。

## 设计依据与技能

- 选定图 `.impeccable/mocks/decision/reading.png`（1586×992），同名 `.png.json` 已 `approved=true`，有用户原话和日期。使用 view_image 再看图。
- 已读并使用 ask-matt、grill-with-docs（grilling/domain-modeling）、impeccable、frontend-design、imagegen、Playwright。问答已结束，进入实施。
- PRODUCT.md 已写真实产品信息和 PC 约束；DESIGN.md 尚未写，技能要求完成后由 documenter 从实际代码记录。
- 约定 `.scratch/ui-polish/direction-contract.md`，正式 surface brief `.impeccable/surfaces/prompt-journal-web-py.md`。
- B 的主要特征：白色横向品牌／项目／搜索／状态导航；蓝灰项目上下文色带；主内容面几乎占满 PC 宽度；目录标题、按会话分组的浅色标题行；对齐的回合编号、时间、绿色状态、查看箭头；分页居中。不是侧栏方案 A/C。
- 预览用合成数据；真实页面不显示“示例数据”标签，不复制假日期／数量，不引入收藏、新建项目等不存在的功能。组内编号必须仍从自己的来源顺序开始。
- 系统中文字体仍用 Segoe UI / Microsoft YaHei。font-match 的自动候选 Unkempt 只是拉丁字体回退造成的排名，不能据此把中文产品改成手写字体或引入外部字体。

## Impeccable 构建阶段（重要）

launcher `C:/Users/614/.agents/skills/impeccable/scripts/impeccable.cmd`。

- 已运行 context，一次即可，不重复。无自动 hook，当前 B 实现结束后要对新 UI 运行一次 detector（上轮被拒绝草稿的 detector [] 不算本轮）。
- seed reference `seed:0801a66e20f5e11f`。
- `.impeccable/build/state.json`：**phase=hero**；comps skipped（已有选定图）、spec closed、plates closed（没有图片素材）。
- 58 区域 map `.impeccable/build/regions.json`，spec `.impeccable/build/spec.json`，所有 14 个文本区域已测量。
- 所有地图错误已修复，最后 map inspection `.impeccable/build/map-inspections/1793066129865838500-61712/`。
- 计划审核 session `ebb0d6d3b6b3c0894bc1eb560b105879efcc7d4ae7310180be917634adc81beb`，用户在聊天明确审核通过后，已按该真实决定在页面录入，`component-review verify --manifest .impeccable/review/components.json` 返回 `visualDecision=approved`。不要伪造或再请求该审核；3512 服务已结束也不影响批准记录。
- scaffold 已生成 `.impeccable/build/scaffold/{layout.css,hero-reference.html}`。scaffold 是测量参考，不是实现，不要直接当成产品。
- 下一步：先把目录首屏做完，以合成数据在 1586×992 捕获 `.impeccable/review/hero-repro.png`，`build-phase record hero` / `build-phase advance` 按输出推进。真实数据与图内假文案不同的适配要如实记录，不要为了截图把假数据写入正式库。后续 sections / motion / responsive / review / document / finish。
- 优先检查 PC 1586、1440、1280 和用户浏览器约1091宽；用户明确不要求手机。该用户指令优先于技能默认手机截图要求，给 finish reviewer 明确 PC-only。
- 技能参考 `reference/new-work.md`、`visualize.md`、`craft-floor.md`、`operate.md`、`region-map.md`、`component-review.md` 已读。后续按阶段查必需部分，避免重复整本加载。

## 已写的代码（尚未验证／发布）

1. **新增 `prompt_journal/presentation.py`**：STYLE tokens／CSS 和静态 `icon(name)`。已有 B 的 header、context-band、workspace、session-group、turn row、status、pagination 样式；也带一部分阅读／搜索基础样式。仅本机 CSS 和小型 SVG，不引入外部资源。
2. **修改 `prompt_journal/web.py`**：
   - 移除旧 STYLE 字符串，从 presentation 导入 STYLE、icon。
   - `context_html()` 第23行附近，创建项目背景区。输入文本全部 escape，project_id quote。
   - `page()` 第37行附近，新横向壳、全局搜索（GET /search）、原导航及状态，main 有 `id=main` 和 tabindex；可见键盘跳转入口。
   - LIVE_SCRIPT 额外更新 indicator.dataset.state，main 自动刷新时同时替换 `#page-context`，避免数量／标题上下文过期。
   - `turn_directory()` 第471行附近，metadata-only 结果按会话分组为默认展开的原生 details。data-key 对来源／会话转义；组头显示“本页 N 个回合”（不能冒充该会话总数，分页可能分组跨页）；行含原链接、来源时间、状态及查看箭头；页码／前后页。
   - `/project/<id>` 第721行附近传入项目 context。当前这行有重复 basename 表达式，可在后续整合 `project_name()`。
3. 最新 `python -m mypy` **17 个源码文件通过**。

尚未做：新代码首屏截图、当前版本的单测／完整测试、阅读来源折叠、首页适配 B、搜索／状态／管理适配、旧会话兼容页 context、一致导航 active、浏览器交互、性能对照、最终 review/document。

### 已知要处理的细节

- `tests/test_turns.py` 旧断言 `directory.split('<main>')[1]` 会因 main 新属性失败，改为 `split('<main', 1)[1]`。注意原语句在 with patch 内 **20空格**，上一轮改错缩进引起导入错误已随旧草稿撤回；本轮尚未修改测试。
- 当前 presentation 的 `.reader .context-band h1` 不会匹配（context 在 main.reader 外）；阅读页延伸时修正结构或 selector，避免长会话标题巨大。
- 目录截图已选行不应伪造状态，产品用 hover/focus 或真实定位表示选择。
- 全局搜索放在 header，不应让原正文搜索表单失去 q/project/scope 控件及懒加载选项。保持 data-search、data-key、data-session-* 等原属性契约。
- 新折叠 metadata 的 evidence 链接保留；长文本 pre 继续是外层 message details 直接子节点，否则 loadLazyInDetails 会失效。
- 任何 source id 写到 data-key 等属性都必须 escape(...,quote=True)。旧未发布草稿的 version_note 漏转义问题已由回退消除，不要复制回来。
- 附件可直接打开；说明／证据可折叠。未提供文件名的 PNG 可准确标“PNG 图片”，不要从图片猜测来源类型。
- 新 SVG 都是小几何图标，无图片素材，不改变 CSP，消息仍转义。

## 正式服务与数据

- **8766 仍是上一次已验收代码，PID 31204，未在本轮重启。**
- 最后健康检查 running=true、sourceAvailable=true、error=null。
- 原 enabledAt **1792940638.277109**，绝不可 `--start-from-now`。
- 正式目录 `C:\Users\614\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\LocalPromptJournal\data`。
- 当前无8797／8798预览监听。后续可用 `serve --port 8797` 对同一正式库做只读预览（不要启动第二采集器），或建源码外合成库8798做 comp 首屏。正式服务更新留到验证完成。
- 已保留清理前备份 `D:\AI\日志验证\dialogue-only-20261027\before-tools-removal.sqlite3`，本轮不再清理或迁移数据库。
- 上一轮正式工具清理后库约592MB，保留当时1506版本，后续对话增长正常；47项测试是旧已验收版本结果，不能当作本轮新 UI 已通过。

## 浏览器与运行产物

- Playwright CLI：`C:/Users/614/AppData/Local/npm-cache/_npx/31e32ef8478fbf80/node_modules/@playwright/cli/playwright-cli.js`，node直接运行，避免 npx.cmd 长参数8191限制。
- 浏览器 session `journal-b`，目前停在本地计划审核完成页；不要再点新的审批。可以 goto 独立预览继续工作。
- 原审查页服务已无3512监听；批准已持久化。旧 exec session39909应已结束，无需继续等待。
- 源码外 `D:\AI\日志验证\ui-refresh-20261027`：旧截图、未批准草稿 `unapproved-draft.patch`、设计探索及预览健康记录，非当前实现证据。
- 新 B 验证建议另建 `D:\AI\日志验证\ui-b-20261027`。截图／真实数据不可加入 Git。
- `.impeccable` 包含生成图、设计地图、font匹配、review运行态等大量本地文件。**不要 git add -A 上传真实截图／运行态。** 最后明确选择源码、测试、文档与可保留的合成设计依据；运行态放 ignore 或留本地。尚无本轮提交。

## 建议接续顺序

1. 看 reading.png 与代码，确认 B 当前首屏骨架。
2. 建合成3会话（3、2、2回合，名称为图中的示例）的源码外库，启动8798；另启8797真实只读预览。
3. 拍1586×992目录，按hero门槛比较，修一批差异后推进阶段；不无限打磨。
4. 完成首页、阅读及来源披露、搜索／状态／管理，保留受控数据／证据安全边界。
5. 运行适当的 tests、最终47项完整套件、mypy，机械 detector 一次；PC 多宽度浏览器检查：原文／懒加载、来源折叠状态跨刷新、附件、搜索高亮、返回、分组／分页、键盘及无溢出。
6. 按技能让 fresh finish reviewer 审查并让 documenter 写 DESIGN.md + .impeccable/design.json。代理模板在 `C:/Users/614/.agents/skills/impeccable/agents/{impeccable_finish_reviewer,impeccable_documenter}.toml`，用 collaboration 子代理而非新用户线程。用户已通过技能授权这些代理。
7. 完成后仅更新8766，沿用原data-dir和启用时间；复核健康与页面，给用户体验入口及事实结果。用户最终体验确认前不 commit/push。

当前没有需要用户再补充的设计或计划问题；继续执行已授权工作。
