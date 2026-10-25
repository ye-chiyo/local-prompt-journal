# 工程技能配置草案（已确认并写入）

已选择：本地 Markdown issue tracker、默认 triage 标签、single-context。用户于 2026-10-25 确认按本草案创建 AGENTS.md；四个文件已写入。下文保留审批时的内容，生效版本以 AGENTS.md 和 docs/agents/*.md 为准。

以下是已确认的内容快照。此文档不是生效的仓库指令。

## 待选择文件：AGENTS.md 或 CLAUDE.md

```markdown
## Agent skills

### Issue tracker

需求与任务使用本地 Markdown。创建、读取或更新任务时，遵循 `docs/agents/issue-tracker.md`。

### Triage labels

使用五种默认 triage 标签。标记任务状态时，读取 `docs/agents/triage-labels.md`。

### Domain docs

使用 single-context 布局。探索领域概念或评估设计决策时，遵循 `docs/agents/domain.md`。
```

## docs/agents/issue-tracker.md

```markdown
# Issue tracker: Local Markdown

本项目的需求、规格与任务保存在 `.scratch/`。

- 每个功能一个目录：`.scratch/<feature-slug>/`。
- 规格：`.scratch/<feature-slug>/spec.md`。
- 每个实现任务一个文件：`.scratch/<feature-slug>/issues/<NN>-<slug>.md`，从 01 编号。
- 任务顶部用 `Status:` 标记状态，标签见 `triage-labels.md`。
- 讨论追加至文件末尾的 `## Comments`。

技能要求发布到 issue tracker 时，在上述目录创建 Markdown 文件；要求读取任务时，按用户提供的路径或编号定位文件。

## Wayfinder

- 地图：`.scratch/<effort>/map.md`，包含 Notes、Decisions-so-far、Fog。
- 子任务：`.scratch/<effort>/issues/NN-<slug>.md`，正文记录问题。
- `Type:` 为 research/prototype/grilling/task；该工作流的 `Status:` 使用 claimed/resolved，尚未领取且未解决的任务为 open。
- `Blocked by: NN, NN` 记录依赖；所有依赖 resolved 后才可领取。
- 按编号选择 open、无未解决依赖、未领取的任务，执行前写入 claimed。
- 完成后追加 `## Answer`，标记 resolved，并在地图的 Decisions-so-far 中追加结论和链接。
```

## docs/agents/triage-labels.md

```markdown
# Triage labels

| 技能角色 | 本地标签 | 含义 |
| --- | --- | --- |
| needs-triage | needs-triage | 待评估 |
| needs-info | needs-info | 需要补充信息 |
| ready-for-agent | ready-for-agent | 定义清楚，可交给 agent 执行 |
| ready-for-human | ready-for-human | 需要人工实施 |
| wontfix | wontfix | 不予实施 |

技能提及角色时使用对应本地标签。项目任务以 `Status:` 行保存状态。
```

## docs/agents/domain.md

```markdown
# Domain docs

本项目采用 single-context：根目录 `GLOSSARY.md` 和 `docs/adr/`。

## 探索前读取

- 读取根目录 `GLOSSARY.md`。若存在 `GLOSSARY-MAP.md`，改为按其中索引读取相关上下文词汇表。
- 读取 `docs/adr/` 中与当前工作有关的决策。
- 文件不存在时直接继续。术语和决策明确后，由 domain-modeling 技能按需创建。

## 使用规则

任务标题、设计、假设和测试名称采用词汇表中的领域术语。
遇到未定义概念，先判断是否重复命名；确有缺口则记录供 domain-modeling 处理。
提案与既有 ADR 冲突时，明确引用对应 ADR 并解释重议原因。
```
