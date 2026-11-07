# UI 去装饰与组件精简记录

日期：2026-11-07

状态：源码实现与预览验收完成；正式 `8766` 已随后重启并验收。

## 目标

删掉排版已经能说明问题的微文案和装饰性容器，保留查找、阅读、搜索、来源证据、删除确认和采集状态功能。

## 删除项

- 首页：页面说明、筛选标签、项目路径展开组件、外层列表卡片、行分隔线。
- 项目页：可见“会话目录”标题与分页说明、目录来源信息组件、回合尺“回合”前缀、已完成回合装饰线、消息角色图标底块、消息 footer 边框、阅读区空状态说明。
- 搜索页：页面说明、查询字段标签、搜索卡片外壳、结果说明句、重复的分页摘要和结果 footer 装饰边框；移除独立的会话名称预筛选输入，保留真正参与查询的项目范围与会话范围下拉。
- 采集状态：卡片外壳、“自动归档 / 本轮结果”重复标题、来源正常说明、对账说明和技术详情说明。
- 容量与删除管理：卡片外壳、重复说明和多余分隔线；删除安全提示仍保留。
- 快捷键弹窗与选择提示：移除装饰性阴影；代码中未发现渐变。

保留项：页面标题、项目/会话/回合数据、搜索结果、异常状态、来源证据、保存版本、删除确认、容量规则与必要表单。

## 验证

- `python -m unittest discover -s tests`：77 项通过。
- `python -m mypy prompt_journal`：19 个源文件无问题。
- Impeccable detector：`[]`（0 条）。
- Playwright 控制台：0 error、0 warning。
- `1440×900` 与 `1091×918` 均无页面级横向溢出。
- `Ctrl+K`、`?`、`Esc`、`[` / `]` 在预览入口实测通过。

### 会话名称预筛选移除

- 删除“筛选会话”输入框及其输入事件、状态恢复和目录查询参数拼接；会话范围下拉仍按项目加载，超过 100 个时可继续“加载更多会话”。
- 正式入口实测下拉加载 `100` 个候选，继续加载后为 `127` 个；页面不存在 `[data-session-filter]`。
- 搜索筛选区调整为两列；`1042×918` 与 `1440×900` 均无横向溢出，Playwright 控制台 0 error、0 warning。
- 本轮完整测试 77 项通过，`mypy` 19 个源文件通过；正式采集器由既有监视器重启为 `PID 14220`，`enabledAt=1792940638.277109` 保持不变。

## 截图

`D:/AI/日志验证/ui-declutter-20261107/`

- `home-before-1440.png` / `home-final-1440.png`
- `project-after-1440.png` / `project-final-1440.png`
- `search-after-1440.png` / `search-final-1440.png`
- `search-filter-removed-1042.png`、`search-filter-removed-1440.png`
- `status-after-1440.png` / `status-final-1440.png`
- `capacity-after-1440.png` / `capacity-final-1440.png`
- `manage-after-1440.png` / `manage-final-1440.png`
- `home-final-1091.png`、`project-final-1091.png`、`search-final-1091.png`、
  `status-final-1091.png`、`capacity-final-1091.png`

## 边界

- 本轮先在独立预览服务 `8767` 验收，随后通过既有监视器重启正式 `8766`；没有提交或推送。
- 手机／平板仍未专项适配；产品以 Windows PC 为主。
