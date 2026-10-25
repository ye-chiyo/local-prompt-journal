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
