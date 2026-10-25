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
