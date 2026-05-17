---
description: 根据 SlotBlueprint 生成 408 单题，并通过代码验算和结构检查收口。
---

# Skill: generate-question-408

## When to use

当任务是根据一个 `SlotBlueprint` 生成 408 单选题或综合应用题时使用。

## Tools

- `search_knowledge_408`
- `generate_question_408`
- `code_exec_408`
- `check_question_408`

## Workflow

1. 读取 SlotBlueprint，确认 `slot_id`、题型、知识点、难度与计算量约束。
2. 如题位经验不足，先调用 `search_knowledge_408` 检索经验卡或真题抽取。
3. 调用 `generate_question_408`，不要手写替代现有 pipeline。
4. 调用 `check_question_408` 检查题目结构。
5. 如果检查失败，只围绕失败字段给出修复目标，不要扩大改动范围。

## Acceptance

- 单选题有四个选项和明确答案。
- 综合题有子问和答案证据。
- 输出中保留 solver evidence 或 review observation。
