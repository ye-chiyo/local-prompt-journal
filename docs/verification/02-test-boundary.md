# 任务 02 验证边界与独立事实

实施基线：`433b8dda996cf1501c5199696657c06ac470bf62`；开工工作区干净。用户验收前不提交、不登记 completed。

沿用任务 01 已确认的公开入口：仅替换外部 Codex 协议进程，真实导入、保存、重开，经 HTTP 页面、公开查询与自包含导出观察。不会测试私有函数、表结构或内部调用次数。

实施前固定的人工事实（固定协议样本不执行其中的命令）：

| 回合／来源身份 | 参数事实 | 结果事实 |
| --- | --- | --- |
| turn-1 / cmd-ok | command=`echo 样本`，cwd=`C:/sample` | `命令原文\n`，completed，退出码 0，耗时 12ms |
| turn-1 / parallel-a | MCP sample/lookup，key=相同 | `甲结果`，completed |
| turn-1 / parallel-b | MCP sample/lookup，key=相同 | 错误 `乙失败`，failed；不能与甲合并 |
| turn-1 / dynamic-long | 动态 sample/long，limit=9000 | 8000 个“长”加末尾 `末尾原文`；不缩写 |
| turn-1 / cmd-cut | command=`echo 截断` | `已取得前缀\nWarning: truncated output`；正文仅为提示，是否实际截断未知，不能把提及警告的文本当作结构化截断证明 |
| turn-2 / missing | 动态 sample/pending，arguments=null（实际 JSON null，不能显示为未提供参数） | inProgress，无结果，完成时间未知 |
| turn-2 / output-only | 独立 functionCallOutput，name=standalone | `独立原文`；无请求参数和执行状态，不猜测与其他调用配对 |
| turn-2 / future | 未支持事件 | 载荷 `未来原文` 可核对，明确不支持 |

同参 MCP 在来源中按 b、a 顺序出现，以固定身份核对；不按文本、位置或关联算法计算正确答案。按验收前确认的分组阅读要求，核对对话消息彼此的来源顺序、工具及其他条目在对应回合“执行过程”内的来源顺序；分组页面位置不冒充所有事件的原始交错顺序。

真实薄契约：继续使用已获选择的 `01a17191-9368-7082-9d36-804621988b6d`。在修改生产代码前，直接通过只读 App Server 取得并固定原始协议记录于运行时 `acceptance/02-raw-before-implementation.json`，独立工具清单为 `02-independent-tools.json`，含 20 个命令与 5 个 MCP 的来源身份、所属回合、完整参数／结果及实际字段。清单不经过 Journal 的解析、查询或导出。此清单只证明当前接口返回的事实；它不能证明接口已覆盖所有底层记录。当前接口未返回独立函数输出及动态工具，相关场景用人工固定样本验证并明确真实兼容性缺口。

操作：导入 → 关闭外部来源 → 新应用实例／新进程重开 → 打开回合并展开工具 → 原始证据 → 下载 JSON，按固定身份逐项比较。保留任务 01 的 38 条消息核对作为回归，不能用它代替本次工具清单。
