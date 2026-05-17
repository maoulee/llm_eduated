# Slot Policy

408 题位逻辑是业务核心，runtime 不得反向接管。

- PaperBlueprint 必须通过 slot contract 和 skeleton checks。
- 单选题必须包含 `stem`、`option_A`、`option_B`、`option_C`、`option_D`、`correct_answer` 或 `answer`。
- 综合题必须包含 `stem`、`sub_questions`、`answer` 或 `correct_answer`。
- `option_style == "none"` 的题位视为综合题。
- 题目修复应优先局部修复，不应无故改变 slot_id、知识点、题型和预算约束。
