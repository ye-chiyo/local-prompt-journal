# PC 设计预览：历史记录

> 本文保留早期方案选择过程，不是当前实施依据。用户后来改选 A，并确认右侧按需阅读；当前要求见 [规格](spec.md) 与 [方向约定](direction-contract.md)，最新图片见 [桌面参考](reference/approved-desktop.png)。下文的「当前状态」仅指当时的历史阶段。

用户要求：重新设计，当前页面单调；先给预览图，同意后才实施，主要适配 PC，无需手机。本轮已停止原 refinement 草稿，正式页面保持已验收版本。

## 供确认的方案

| 方案 | 核心布局 | 预览 |
| --- | --- | --- |
| A 分区工作台 | 深蓝项目栏、中间分组回合目录、右侧会话基本信息 | [atlas.png](../../.impeccable/mocks/decision/atlas.png) |
| B 通透内容台 | 顶部导航、项目上下文、完整宽度分组目录 | [reading.png](../../.impeccable/mocks/decision/reading.png) |
| C 回合导航台 | 独立项目索引、强对比导航、会话内回合序列 | [route.png](../../.impeccable/mocks/decision/route.png) |

次级标准布局参考 `standard.png`。图片中的名称、数量、日期与状态均为合成示例；不是运行页面截图，不作为新增产品功能或真实数据证明。正式实现仍按会话内来源顺序独立编号，目录不预读正文，原文与附件保持。

每张图旁的 `.png.json` 保存精确绘图说明，`approved=false`；PNG 内亦嵌入来源提示。A、C 初稿中不符合加载／功能范围的内容已在正式交付预览中修正；生成工具原图仍留在生成目录，非选定方案。

## 当前状态

2026-10-27：用户明确回复“B · 通透内容台，同意实施”。选定图为 reading.png，其 sidecar 已 approved=true；A、C 与标准参考未选定。后续实现以 B 为准。

实施计划已测量并建档，纯文字／控件／几何图标，无图片素材；当前 impeccable 要求在本地计划检查页确认后才能进入页面代码，见任务最新 Comments。下列条目保留预览交付时的阶段记录。

- 确认方式：聊天中的图片及结构化选择，允许选定、组合、修改或整组重做。
- 等待用户明确同意之后才进行新的界面代码实现。选定后才写设计实施约定和样式规范。
- 种子参考 `seed:0801a66e20f5e11f`，方向记录保存在源码外 `D:\AI\日志验证\ui-refresh-20261027\design-exploration.md`。
- 正式源码 `web.py`、`tests/test_turns.py` 与已验收 HEAD 逐字节一致；原不发布草稿补丁在同一源码外验证目录。8766 running=true、sourceAvailable=true、error=null，原 enabledAt 不变。
- 主要工具：grill-with-docs、impeccable、frontend-design、imagegen；本阶段只完成预览，不宣称新界面已经实现或验收。
