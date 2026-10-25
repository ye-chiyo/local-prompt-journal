# AI Agent 日志项目：GitHub 可复用方案调研

调研日期：2026-10-25（Asia/Shanghai）。第一版目标已确定为当前 Codex 桌面端。

用户随后确认：主要用途是改进提示词，日志必须全部留在本机。因此优先考虑本地查看、标注与比较；候选中的云端提示改写/模型分析/同步不属于当前范围。推荐路线与验收见 [方案草案](project-design.md)。

本次只读取公开项目 README、使用文档和许可证，没有安装候选软件，没有读取个人会话，也没有做运行兼容性测试。以下“支持”首先指项目文档声明，不能视为对当前 Codex 桌面版本的实测认证。

## 核心判断

已有工具能够从本地会话记录展示用户消息、AI 输出和工具执行过程。第一步应该验证现有数据源和解析器覆盖率，而非先搭数据库或让 agent 额外写日志。对于个人 Codex 历史复盘，优先试验本地查看器；对于自己开发、能插桩的 agent，才优先考虑 Langfuse、Phoenix、AgentOps。

**关键兼容性门槛：下面三个 Codex 查看器文档都以本地 rollout JSONL 为主要输入。** 主线程在当前环境发现了向分页 thread history 迁移的迹象，因此不能假设所有当前桌面会话仍有完整 JSONL。必须先用一个合成测试会话确认实际存储来源、读取接口和事件覆盖，再选择复用方案。该门槛是本次调研结合当前环境得到的工程判断，不是候选项目已宣布兼容或不兼容新格式。

## 六个优先候选

| 项目 | 接入方式与有价值的能力 | 对本项目的适配结论 | 许可证 |
| --- | --- | --- | --- |
| [AgentXRay](https://github.com/alloevil/AgentXRay) | 读取现有本地日志；工具参数/结果、后台进程退出关联、编辑前后验证顺序、原始证据链接；可离线生成 JSON 报告 | 最接近“事后定位问题”的目标，可优先比较诊断模型与解析器；仍需当前桌面格式验证 | MIT |
| [Sessions Viewer](https://github.com/jerrywu001/cc-sessions-viewer) | Windows/macOS/Linux 桌面查看器；多 agent 会话、工具配对、导出、历史整理 | 最适合快速体验“我需要怎样的浏览界面”；全局搜索范围有限 | MIT |
| [Codex Trace](https://github.com/PixelPaw-Labs/codex-trace) | 专门读取 Codex CLI JSONL；会话/消息搜索、工具与输出、协作链、SSE 实时追踪 | 如果当前会话仍可导出兼容 JSONL，是较聚焦的查看器候选 | MIT |
| [Langfuse](https://github.com/langfuse/langfuse) | SDK/框架集成/数据接入；trace、会话、提示词版本、评估、数据集；可自托管 | 可作为未来分析后端；不能仅安装就自动获取任意桌面 agent 完整历史 | 核心 MIT，ee 目录等例外 |
| [Phoenix](https://github.com/Arize-ai/phoenix) | OpenTelemetry/OTLP 与 OpenInference 插桩，trace、评估、实验、标注 | 若未来自己开发 agent 或建立标准 trace 导出器，值得考虑；当前桌面采集问题仍要另解 | ELv2 |
| [AgentOps](https://github.com/AgentOps-AI/agentops) | SDK 初始化、框架集成、操作装饰器；执行图、输入输出、异常和成本 | 更适合可修改代码的 agent 应用；不是通用桌面会话抓取器 | MIT |

### 1. AgentXRay：最贴近复盘证据链

README 明确将其定位为本地现有日志读取器，核心读取/inspect 不调用模型。支持浏览工具参数与结果、子 agent、记录中的 token；对 Codex 可关联 exec_command 启动、write_stdin 轮询与退出。检查“测试通过后又修改、却未记录后续验证”这样的时间关系，比只统计错误数更符合用户目标。[README](https://github.com/alloevil/AgentXRay/blob/master/README.md)

使用文档列出 Codex 输入为 `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`，有增量会话备份功能。离线 inspect 支持 Codex、OMP、Claude Code，输入为稳定 UTF-8 JSONL，单文件上限 64 MiB。看板支持某个平台不代表离线诊断覆盖相同。[使用文档](https://github.com/alloevil/AgentXRay/blob/master/docs/usage.md)、[离线接口文档](https://github.com/alloevil/AgentXRay/blob/master/docs/offline-inspect.md)

边界：它不证明任务完成、不自动确定根因，也不证明测试覆盖修改；缺记录应保持 unknown。README 公开的真实 Codex 例子只有一个冻结快照，不能据此保证泛化准确率。可选提示词改写等功能会连接配置的模型端点，不能把整个产品说成绝对离线。Node.js 要求至少 22.13；本次未实测 Windows。[README](https://github.com/alloevil/AgentXRay/blob/master/README.md)、[MIT LICENSE](https://github.com/alloevil/AgentXRay/blob/master/LICENSE)

**值得复用：事件与原文位置关联、保守的 unknown 状态、过程退出与工具调用分层、验证顺序规则。** 不宜未经覆盖率验证直接把它的结论当任务评分。

### 2. Sessions Viewer：快速验证浏览体验

README 提供 Windows x64 安装包，支持读取 Codex 等七种来源，展示支持的工具配对、diff、图片和导出 Markdown/HTML/解析后 JSON。读取、搜索、导出不改原始会话；重命名、删除/恢复、继续对话是另行写操作。历史处理本地完成，但价格、更新、聊天等功能可能联网。[README](https://github.com/jerrywu001/cc-sessions-viewer/blob/main/README.md)、[MIT LICENSE](https://github.com/jerrywu001/cc-sessions-viewer/blob/main/LICENSE)

重要限制：全局搜索查标题与用户提示，不查 AI 回复或工具输出；解析后 JSON 不等于原生备份；导出图片可能仍是外部链接。官方项目文档按 rollout JSONL 说明 Codex 适配，并注明文档中的适配器审查不代表当前安装版本的端到端认证。[Codex 使用指南](https://sessions-viewer.js-bridge.com/guide/codex-session-viewer)

**值得复用：原生桌面体验、用户提示导航、会话整理。** 若目标是从所有工具错误文本检索历史问题，现有全局搜索范围不够。

### 3. Codex Trace：聚焦 Codex 的本地实时查看

README 将输入明确为 Codex CLI 本地 JSONL，能显示工具调用、命令输出、MCP、补丁、协作链和 token，并提供消息搜索与 SSE 实时追踪。提供桌面和 Web 模式，README 指向 Windows/Linux 构建。无需向外部服务发送 trace。[README](https://github.com/PixelPaw-Labs/codex-trace/blob/main/README.md)、[MIT LICENSE](https://github.com/PixelPaw-Labs/codex-trace/blob/main/LICENSE)

其支持不同年代 JSONL 元数据的声明，并不能证明支持新的分页历史存储。没有实际安装验证，也没有验证源码中每一种工具事件的配对正确性。

**值得复用：Codex 专用解析和实时浏览。** 它主要解决查看，长期入库、脱敏、保留策略与故障恢复仍需评估。

### 4. Langfuse：成熟分析后端，采集仍需接入

通过 SDK、框架集成或 API 写入 trace，提供提示词版本、评分、数据集和实验等能力，可自托管。SDK 使用后台排队与批量发送；这支持把采集与模型上下文分离，但不能等同于完全零资源开销。[README](https://github.com/langfuse/langfuse/blob/main/README.md)、[Observability 官方文档](https://langfuse.com/docs/observability/overview)

本项目可以以后把规范化事件导出到 Langfuse；这属于需要开发并验证的适配路线，不能把“后端支持 trace”误写成“现成支持此桌面端全部会话”。根许可证明确将若干 ee 目录排除出 MIT 范围。[LICENSE](https://github.com/langfuse/langfuse/blob/main/LICENSE)

**值得复用：评分/评估/实验和 trace 展示。** 不建议个人首版为了存日志就立即引入整套平台。

### 5. Phoenix：标准 trace 路线

Phoenix 接受 OTLP，使用 OpenTelemetry/OpenInference，支持多框架自动或手动插桩，并提供会话、标注、指标。可在本地或容器部署。其“让 coding agent 帮你安装 tracing”是让 agent 修改待观测应用的接入方式，不能理解成自动读取 coding agent 自己的完整历史。[README](https://github.com/Arize-ai/phoenix/blob/main/README.md)、[Tracing 官方文档](https://arize.com/docs/phoenix/tracing/llm-traces)

当前根许可证是 **Elastic License 2.0**，不是 Apache/MIT；许可证明确对向第三方提供实质功能的 hosted/managed service 设限。如果之后想将本项目做成收费托管产品，需要重新核对所用组件的许可范围。[LICENSE](https://github.com/Arize-ai/phoenix/blob/main/LICENSE)

**值得复用：标准事件导出与评估工作流。** 对当前个人 Codex 桌面采集不是最短路径。

### 6. AgentOps：自建 agent 的应用级追踪

README 展示 SDK 初始化、多个框架集成，以及 session/agent/operation/workflow 装饰器；支持记录输入输出、异常、异步函数和生成器。项目提供 Dashboard/API 后端自托管说明。[README](https://github.com/AgentOps-AI/agentops/blob/main/README.md)、[MIT LICENSE](https://github.com/AgentOps-AI/agentops/blob/main/LICENSE)

**值得复用：应用内部执行图和操作层追踪。** 需要应用侧集成；文档中的“两行代码”不构成记录所有自定义工具与任意桌面平台的完整性保证。

## Claude Code 备选参考

- [claude-code-log](https://github.com/daaain/claude-code-log/blob/main/README.md)：MIT；读取 JSONL，生成 HTML/Markdown/JSON，支持 watch、服务端归档全文搜索、工具结果、子 agent 和分叉。Codex CLI 单会话支持明确标为 beta，不能据此保证桌面端兼容。[许可证](https://github.com/daaain/claude-code-log/blob/main/LICENSE)
- [claude-code-transcripts](https://github.com/simonw/claude-code-transcripts/blob/main/README.md)：README 标注 Apache-2.0；JSON/JSONL 转静态 HTML，可保留原始 JSON；归档子 agent 需要显式 include。README 特别说明 web 命令因非官方接口变化当前失效。它是“依赖非稳定抓取接口会失效”的直接案例，适合借鉴静态归档，不是 Codex 优先方案。

## 建议的选型验证顺序

1. 创建合成会话覆盖：两条用户提示、普通回答、一次成功工具、一次失败工具、长输出、后台任务、中途取消、子 agent；仅用无敏感数据的样本。
2. 确认当前 Codex 桌面真正留下了哪些事件，以及是否仍有完整 rollout；同时保留 native 原始记录与导出记录，明确缺失项。
3. 用 AgentXRay 与一个简单查看器比较同一份样本；先对齐记录数、原文、call ID 和父子关系，再比较界面。
4. 若已满足大部分需求，采用现成查看器，加一个独立的可靠归档/索引层。若格式不兼容，先做格式适配器，避免同时重做前后端。
5. 只有出现跨用户协作、规模化评分、长期实验比较需求，再接 Langfuse/Phoenix/AgentOps。

这些是本次调研的设计建议，不是已经完成的安装、性能测量或兼容性测试。
