# 任务 05：关联证据与交验

当前状态：2026-10-26（Asia/Shanghai），用户在自动入库调整及重启验证交验后明确回复“审核通过”。任务 05 已登记 Execution: completed，本次将相关实现、必要测试和交付记录一次提交；不推送、不进入后续任务。下文未验收文字及 userAccepted:false 均为验收前的过程记录，原始验证报告保持原样，来源验证边界不变。

实施基线：`master` / `8f029aa19fcac3ecf30030cc0137a7e86a0cf7ac`。开工工作区干净，8766、8767 未监听。2026-10-26（Asia/Shanghai）。本次仅实施任务 05；用户体验确认前不提交、不登记完成。

## 实施前固定事实与验证边界

沿用已确认的公开边界：只替换外部 Codex 协议进程，经公开导入／自动采集、真实保存、重开、HTTP 查询、浏览器及导出观察。不测试内部表、私有方法或内部调用次数。

人工固定协议事实（不执行样本中的命令）：

| 会话／回合／条目 | 独立事实与预期 |
| --- | --- |
| main / t1 / ok | 命令 `sample identical`，processId=7；首次 inProgress、输出“启动原文”；随后同一条目 completed、exitCode=0、输出“启动原文\n结束原文”。当前视图有退出证据，旧运行证据保留。 |
| main / t1 / fail | 相同命令，另一个条目、processId=8，failed、exitCode=9、输出“失败原文”；不能与 ok 合并。 |
| main / t2 / unknown | processId=7 被再次使用，但条目和回合不同；completed、无退出码、输出“只有启动回执”。退出结果未知，不能与 t1 / ok 合并。 |
| main / t2 / running | 独立条目 processId=11，inProgress、无退出码、输出“仍在运行原文”；展示来源最后记录仍在运行，最终结果未知。 |
| main / t1 / activity | subAgentActivity，agentThreadId=child，kind=started；另有 agentThreadId=missing 的活动和缺 agentThreadId 的不完整记录。 |
| child | parentThreadId=main；自己的项目 `D:/子项目`，自己的用户原文“子会话原文”。先保存 child 再保存 main，不以到达顺序断言因果。 |
| fork | forkedFromId=main；自己的用户原文“分叉原文”。与子 agent 不混淆。 |
| grandchild | parentThreadId=child，已归档；从 main 包含关联导出只取一层，不递归包含 grandchild 正文。 |
| missing / blocked | missing 未归档；blocked 由来源报告不可读取。关系页面及导出不尝试取得目标正文。 |
| old-child / old-fork | 只有正式枚举元数据分别给出 parentThreadId=main、forkedFromId=main；回合开始100、updatedAt100，早于启用190，正文禁止读取。仍显示两条关系及“正文未归档”，导出保存无正文关系字段投影。 |

不完整协议记录另固定一个 collabAgentToolCall：senderThreadId=main、receiverThreadIds=[child]、缺 tool。应标明关系类型未知与缺失字段，不能当作 spawnAgent 或分叉。

追加同一来源不同会话、相同条目／processId 的独立执行，预期仍保留本会话边界。来源无独立轮询条目时，固定样本也不伪造此类字段；只验证原子命令条目的保存修订、退出证据和明确缺口。

真实薄契约独立于受控行为：现有已授权材料中，主会话 `01a17191-9368-7082-9d36-804621988b6d` 的三条 subAgentActivity 均指向 `01a17195-df8c-7a21-96d8-fe592599ad7e`，活动为 started、interacted、completed；目标尚未归档，不读取其启用前正文。20 条 commandExecution 均有 processId 及 exitCode=0。依据是已有原始协议证据，不是应用的关系输出。当前本机 schema 定义 parentThreadId（仅子 agent）、forkedFromId（分叉来源）、subAgentActivity.agentThreadId 及 commandExecution.processId（底层 PTY 身份）；后者未承诺全局唯一，也不证明独立后台启动或轮询。

真实来源不暴露的包装／嵌套调用不构树。commandExecution 历史没有独立轮询调用身份；同一条目修订的保存顺序只表示观察顺序。受控样本通过不能认证真实分叉、独立轮询或全部版本覆盖。

## 实现与实际验证

使用既有 Matt setup、implement、tdd 工作流；不更改工程配置。新 `topology.py` 只投影已取得的正式字段，不连接来源。旧归档可直接显示关系；自动采集保留新增关系元数据字段，仍丢弃列表 preview。元数据投影与完整原始响应在页面中明确区分。没有增加读取命令或放宽白名单，也没有回补关联目标正文、重置启用时间或安装登录启动项。

三项公开场景保护命令修订／身份与未知退出、自动归档关系与会话边界、一层关联导出。成功退出码 0、失败退出码 9、复用句柄但不同回合的未知退出、同命令独立条目及其他会话均保持独立。重复读取不拼接累计输出；先前运行状态、当前退出及原始证据保留。缺退出码的完成回执在执行面板和工具卡片均显示未知。关系缺失字段与未知类型不猜配。

真实浏览器已实际打开主会话、展开执行过程与保存观察、查看旧运行输出与成功退出、失败及未知退出；进入 child、返回、进入 fork、返回；两种导出均通过表单实际下载。包含关联后的正文只有 main、child、fork，不含 grandchild 或 missing，遗漏范围在 exportScope 明示；各自消息、工具、修订及原始证据保持边界。选择导出范围在自动刷新后保留。真实页实际展开一条命令并点击原始证据，身份与预先固定条目一致。最后版本的复测与截图见下方交验状态。

原有独立清单回归：38 条消息、108 个来源条目、25 条工具的参数／结果及原始证据一致，两个新进程重开、公开查询与导出一致，原始载荷及 SHA-256 均通过。没有重新导入真实旧会话。最终完整行为检查 21 项通过（原 18 + 本次 3，9.728 秒），mypy 检查 8 个生产文件通过，git diff --check 通过。

## 真实来源薄核对与未验证部分

本机仍为 Codex Desktop/0.164.0-alpha.11.1，与已读取 schema 版本一致。只读元数据枚举可见 1054 个会话，响应提供 source、parentThreadId、forkedFromId 字段；此次枚举 parentThreadId 与 forkedFromId 非空数均为 0，不能宣称真实分叉兼容性通过。未保存列表 preview，没有为追关系读取其他旧正文。

已授权主会话的三条真实活动与事先记录的目标及 started/interacted/completed 一致；20 条命令的正式 processId 与退出码可核对，均取得 exitCode=0。实际子会话正文未获授权归档，因此提供缺失说明，不打开或补读。真实独立后台启动／轮询链、真实分叉正文、全部协作工具种类与所有安装版本未认证。当前版本只支持已独立暴露的命令原子条目修订；没有把固定样本通过称为真实覆盖率认证。

真实数据目录沿用 `C:/Users/614/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/LocalPromptJournal/data/`，启用时间仍为 `1792940638.277109`。受控演示单独位于相邻 acceptance/05-preview/data，人工 1970 年样本时间不代表真实业务。运行报告、浏览器下载及截图均留在源码外 acceptance 下，不纳入提交。

## 交验过程（验收前记录）

当前未获用户验收，未提交、未登记 Execution: completed。双轴审查基于开工基线至全部未提交修改和新增文件，不创建临时 commit。Standards 初审无明确违反或需处理 smell；Spec 初审发现两个问题并修复：未归档旧目标的关系元数据现保存为无正文投影，保留原始字段与投影哈希，不读取预览／旧正文；关联导出按所有者身份及保存版本定位对应修订，未包含版本时明确 evidenceRef=null 及原因，避免并发更新指错证据。复用原三项公开场景复测，新增旧子会话／旧分叉独立事实且外部来源拒绝读取旧正文，没有另堆测试。Standards 复核：明确违反 0、需处理 smell 0。Spec 复核：两项初审发现已修复，未解决发现 0；小文案建议已采纳。两轴分别报告，不以检查通过代替用户验收。

最终服务已重启至当前源码。真实自动采集服务 8766 继续沿用原数据目录与启用时间，公开状态为运行中、来源可访问；受控服务 8767 与真实数据分开。最新浏览器复测完成 main → child（所属项目 D:/子项目）→ 返回 → fork → 返回；运行中、退出未知及元数据旧目标的缺失说明可见。old-child 卡片没有正文入口，实际点击关系证据打开正式元数据投影，未包含 preview 或 turns；截图已视觉检查。两种导出再次通过浏览器实际下载，20 个关系证据指针逐条匹配来源字段，所有原始响应与哈希、关系投影哈希均一致，未出现禁止补读的旧正文。

并发修复另经公开导入／导出复测：外部协议来源连续更新 child 16 次，期间导出20次，无错误关系引用，其中3次证据定位到保留的旧修订；未包含版本的 null 分支经审查核对，本次并发运行没有触发该分支，不虚报实测覆盖。未新增测试套件或内部结构断言。

运行报告为 acceptance/05-real-contract.json、05-{messages,tools}-regression.json、05-concurrent-export.json，以及 05-preview/browser-export-report.json；实际浏览器下载为 05-preview/browser-{single,related}.json，截图为 current-running.png、old-target-metadata.png。报告均保留 userAccepted:false，人工验收未发生；HEAD 仍为开工基线。

真实入口：`http://127.0.0.1:8766/session/01a17191-9368-7082-9d36-804621988b6d`；受控完整演示：`http://127.0.0.1:8767/session/main`。

若自行重启真实服务，先进入项目目录，再沿用原数据目录和启用时间：

```powershell
Set-Location -LiteralPath 'D:\AI\日志项目'
python -m prompt_journal --data-dir 'C:\Users\614\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\LocalPromptJournal\data' run --port 8766
```

不再次使用 --start-from-now。用户明确表示通过／可以提交后才登记完成并创建一次相关 commit，不自动 push 或进入后续任务。

## 2026-10-26 用户体验修正：自动写入本机数据库

用户在页面下载区域反馈“不需要手动下载，自动写入数据库”，并要求自带数据库。本节覆盖上文旧版页面下载体验说明：现有 SQLite 及采集自动入库机制继续使用，页面移除下载按钮、范围表单和对应刷新状态代码。首页、项目页与会话页的状态区展示当前 `app.database` 的真实完整路径，说明无需另装数据库及采集服务运行时自动保存；会话显示已入库及快照最近保存时间。运行／停止、来源可访问性、保存错误及首次范围说明保留。CLI／HTTP 可选导出仍兼容原有单会话和显式一层关联范围，不参与自动入库流程。

公开接口验证在服务重启前记录真实固定样本及受控主会话的消息、工具、savedAt 哈希与 enabledAt；随后两服务重新进程启动、沿用原数据库，重新读取公开视图核对。两份记录完全一致；正式样本仍为38条消息、25次工具记录，正式 enabledAt 仍为1792940638.277109，两个采集器均运行。报告位于源码外 acceptance/05-database-{before-restart,restart-report}.json，未通过数据库内部表制造预期，也未下载或重新导入以恢复记录。

真实浏览器分别打开8766正式页和8767演示页，核对实际数据库路径、运行中状态和本会话已入库时间，确认手动下载控件消失。演示页1091×918和390×844截图已视觉检查，长路径换行，未挤出页面。截图位于源码外05-preview/database-{desktop,mobile}.png。页面仍按既有范围展示来源限制；演示中的blocked与1970时间为受控事实，不能当作正式来源错误。

只调整既有HTTP用户场景的页面预期，测试数量仍为21，完整套件21项通过；mypy检查8个源码文件通过；git diff --check通过；页面检测无报告。增量Standards复核硬性违反0、需处理smell0；增量Spec复核未解决发现0。状态仍为等待用户体验确认，未登记完成、未提交。
