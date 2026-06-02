---
description: 审核 408 题目结构、答案一致性和 slot 契约符合度。
---

# Skill: review-question-408

## When to use

当任务是审核、修复或决定是否接受生成题目时使用。

## Tools

- `check_question_408`
- `python_exec`
- `search_knowledge_408`

## Workflow

1. 先调用 `check_question_408` 做确定性结构检查。
2. 对计算型答案，必要时调用 `python_exec` 复核关键结果。
3. 将问题分类为 `question`、`answer`、`rubric` 或 `blueprint`。
4. 只给出最小修复指令，避免重写已经符合 slot 的内容。

## Acceptance

- 无 hard violation。
- 答案和 solver evidence 一致。
- 修复指令能定位到字段或子问。
