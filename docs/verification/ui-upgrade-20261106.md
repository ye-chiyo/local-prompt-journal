# UI 升级与浏览器验证记录

日期：2026-11-06

状态：方案 A 已实施，正式 `8766` 服务已重启并通过入口验收；未提交、未推送。

## 范围

本轮将 PC 界面升级为「本地档案阅读台」：

- 方案 A 的暖灰纸张、苔绿导航、衬线标题和轻分隔阅读排版；
- 方案 B 的常驻项目索引、顶部项目上下文带、会话目录与阅读区布局；
- 横向回合尺替代占纵向列；
- `Ctrl+K` 聚焦正文搜索、`[` / `]` 切换回合、`?` 查看快捷键；
- 首页、项目工作台、独立回合、搜索、采集状态、容量和删除管理共享同一视觉系统。

产品范围、数据库、采集、搜索、导出、删除、容量和原文保存逻辑未扩大或改写。

## 实现证据

- 共享视觉令牌与新布局：`prompt_journal/theme.py`
- 页面结构、回合尺、搜索和状态分组：`prompt_journal/web.py`
- 搜索命中来源时间：`prompt_journal/search.py`
- 图标：`prompt_journal/presentation.py`
- 设计系统：[DESIGN.md](../../DESIGN.md)
- 视觉检查：[design-qa.md](../../design-qa.md)

## 自动验证

- `python -m unittest discover -s tests`：77 项通过。
- `python -m mypy prompt_journal`：19 个源文件无问题。
- `python -m compileall -q prompt_journal`：通过。
- 首页、项目页、搜索结果页、采集状态页分别运行 Impeccable URL 检测；
  首轮发现文字尺寸、对比度和一条嵌套容器告警，修复后复检为 0 条。
- Playwright 控制台：0 error、0 warning。
- 独立 Impeccable 成品复审：5 项定向问题全部 `resolved`，处置为 `ship`。

## 浏览器验证

真实数据来自正式本机归档；使用独立 `serve` 实例
`http://127.0.0.1:8767`，不启动第二个采集器，不改 `enabledAt`。

在 `1440×900` 与 `1091×918` 下检查：

- 首页、项目工作台、回合正文、搜索、采集状态、数据库容量、删除管理；
- 所有检查页面 `scrollWidth == innerWidth`，无页面级横向溢出；
- 项目阅读区宽度为：`1440px` 下约 `847px`，`1091px` 下约 `566px`；
- 搜索结果首条卡片顶部由旧结构的约 `589px` 提前到约 `428px`；
- 搜索带项目范围时持续显示“当前范围”和“清除筛选”，高级筛选默认收起；
- 首屏项目上下文、会话标题和回合位置均可见；
- 采集状态首屏显示运行状态、最近检查、结果数量及分组后的失败摘要；
- 本轮发现数可对账，已保存但未返回与删除排除单独列示，停止态使用中性色。

交互实测：

- 全局搜索：`Ctrl+K` 聚焦 `#global-search`；
- 回合键盘切换：`]` 从回合 1 切到 2，`[` 返回上一回合；
- 快捷键说明：`?` 打开原生 dialog，`Esc` 关闭；
- 项目筛选：输入 `codex` 后显示 `6 / 14` 个匹配项，并更新状态文本；
- 搜索范围：项目筛选与查询同时存在时显示范围标签和清除入口；
- 采集诊断：展开分组后同时可见会话可读名称与技术 ID；
- 键盘焦点：跳转链接与品牌入口均有 2–3px 可见轮廓；
- 减少动态效果：模拟 `prefers-reduced-motion: reduce` 后过渡时长为 `0.01ms`。

## 截图

最终截图保存在源码外：

`D:/AI/日志验证/ui-upgrade-20261106/final/`

- `home-1440.png`、`project-empty-1440.png`、`project-reader-1440.png`
- `search-1440.png`、`search-filtered-1440.png`、`status-1440.png`
- `shortcuts-1440.png`
- `home-1091.png`、`project-reader-1091.png`
- `search-1091.png`、`search-filtered-1091.png`、`status-1091.png`

旧 `8766` 进程与新 `8767` 实现的同尺寸比较：

`D:/AI/日志验证/ui-upgrade-20261106/before-after/`

- `project-before-after.png`
- `search-before-after.png`

## 正式入口验收

验收时间：2026-11-06 10:38–10:47（Asia/Shanghai）。

- 使用既有 `desktop-monitor.stop` 信号停止旧采集器 `PID 18220`；
  桌面监视器 `PID 12544` 自动拉起新采集器 `PID 30104`，没有另起监视器或第二采集器。
- `8766` 仅有一个监听者；采集器父进程为 `12544`，与 `desktop-monitor.pid` 一致；
  停止文件、退出文件均已清理。
- `/api/status`：`running=true`、`sourceAvailable=true`；
  `enabledAt` 在重启前后均为 `1792940638.277109`；正式入口持续产生新的成功归档。
- 以下入口均返回 HTTP `200`：`/`、`/search?q=hook`、`/status`、`/capacity`、
  `/manage/exclusions`、`/api/status`、`/api/version`、`/live.js`。
- Playwright 在 `1440×900` 与 `1091×918` 下检查首页、项目阅读区、搜索结果、采集状态和
  独立回合页；所有页面无横向溢出，控制台 `0 error / 0 warning`。
- 正式入口项目阅读区在 `1440px` 下约 `847px`，在 `1091px` 下约 `566px`；
  横向回合尺自身也不溢出。
- 交互实测：`Ctrl+K` 聚焦全局搜索，`?` 打开快捷键说明，`Esc` 关闭说明，
  `]` 从回合 1 切到回合 2；独立回合页恢复“日志项目 AI”项目上下文与目录返回链接。
- 正式入口截图与机器可读摘要：
  `D:/AI/日志验证/ui-upgrade-20261106/formal-acceptance-20261106/`

## 已知边界

- 本轮只重启采集器，未提交、未推送，也未改写正式数据目录或执行删除／容量写入。
- 未进行手机／平板专项适配；产品明确以 Windows PC 为主。
- 未进行真实屏幕阅读器音频测试，只检查了 DOM、焦点、ARIA 与可见状态。
