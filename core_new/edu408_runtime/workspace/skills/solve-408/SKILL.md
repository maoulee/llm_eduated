---
description: 使用 code_exec_408 对 408 题目答案进行可追溯验算。
---

# Skill: solve-408

## When to use

当需要验证单题答案、执行计算脚本、复跑已保存脚本或比较计算结果时使用。

## Tools

- `code_exec_408`

## Workflow

1. 对短小 CodeAct 片段使用 `execution_mode="sandbox"`。
2. 对需要保存证据的完整脚本使用 `execution_mode="subprocess"` 且 `persist=true`。
3. 每次执行后读取 stdout/stderr，失败时根据 observation 局部修复代码。
4. 最终答案必须引用最后一次成功执行的输出或明确说明执行失败。

## Notes

`code_exec_408` 是唯一代码执行入口。不要直接调用 subprocess 或临时 shell。
