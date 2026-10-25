# 本地 Codex 日志项目：规格与任务

发布日期：2026-10-25（Asia/Shanghai）。用户已确认任务粒度和阻塞关系。

[正式规格](spec.md) 是功能范围与验收边界的依据。下表提供任务入口；当前状态以各任务文件为准。

| 编号 | 任务 | Blocked by |
| --- | --- | --- |
| 01 | [读取一段真实会话并在本机查看、导出](issues/01-single-session-proof.md) | 无 |
| 02 | [查看工具参数、结果与执行状态](issues/02-tool-evidence.md) | 01 |
| 03 | [选择项目与会话的采集范围](issues/03-capture-scope.md) | 01 |
| 04 | [持续同步并在中断后补回记录](issues/04-incremental-recovery.md) | 02、03 |
| 05 | [关联后台任务、子 agent 与分叉会话](issues/05-execution-topology.md) | 02、03 |
| 06 | [用中文搜索提示、回答和工具结果](issues/06-chinese-search.md) | 02、03 |
| 07 | [标注结果并关联后续纠正](issues/07-feedback-corrections.md) | 01 |
| 08 | [保存提示版本并比较使用案例](issues/08-prompt-versions.md) | 07 |
| 09 | [归档附件并导出可离线核对的会话包](issues/09-offline-evidence-export.md) | 05 |
| 10 | [删除受管理日志并阻止自动重新导入](issues/10-managed-deletion.md) | 04、08、09 |
| 11 | [验证首版完整复盘流程与本机运行边界](issues/11-release-verification.md) | 04、06、10 |

## 执行规则

所有任务发布时均标记 ready-for-agent；只有阻塞任务完成后才能开始相应任务。发布时唯一无依赖的任务是 01。

01 必须通过真实数据源的关键记录读取验证；仅固定样本通过不能解锁后续任务。每张任务自行验收其完整功能链路，11 汇总跨功能和运行环境验证。

本次只发布已批准任务，不代表已开始编码，也不代表真实数据源兼容性已通过。
