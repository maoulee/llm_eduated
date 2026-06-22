---
description: 使用 python_exec 对 408 题目答案进行可追溯验算。
---

# Skill: solve-408

## When to use

当需要验证单题答案、执行计算脚本、复跑已保存脚本或比较计算结果时使用。

## Tools

- `python_exec`

## Workflow

1. 传入 `code` 执行验算代码；需要保存证据时传 `persist=true` + `slot_id` + `step`。
2. 需要重跑已保存脚本时传 `file_path`。
3. 每次执行后读取 stdout/stderr，失败时根据 observation 局部修复代码。
4. 最终答案必须引用最后一次成功执行的输出或明确说明执行失败。

## Notes

`python_exec` 是唯一代码执行入口。不要直接调用 subprocess 或临时 shell。
