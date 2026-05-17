---
description: 根据教师需求和 408 题位模板生成 PaperBlueprint。
---

# Skill: compose-paper-408

## When to use

当任务是组一张 408 试卷、规划题位、分配难度或生成 PaperBlueprint 时使用。

## Tools

- `compose_paper_408`
- `check_question_408`

## Workflow

1. 将教师需求保持为原始约束，不要提前改写成泛化目标。
2. 调用 `compose_paper_408` 生成 PaperBlueprint。
3. 调用 `check_question_408` 检查预算和题型字段协议。
4. 如果出现 hard violation，返回具体 slot 或 global budget 问题。

## Boundary

不要让 runtime 自行发明 slot 规则；slot contract 与 skeleton checker 是最终约束。
