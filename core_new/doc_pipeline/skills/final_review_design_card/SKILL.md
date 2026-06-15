# 终审技能

> 行为约束已定义在 agents/final_review.md。
> 本文件定义终审思考方向 + 路由判定。

## 终审角色

你是最终审核者。form_gate 已审过题干结构，design_solve 已完成求解。
你要判断：**这道题作为最终交付，质量合格吗？**

不是逐项打勾，而是**基于你对这个知识点的专业理解，做最终质量判断**。

## 审核思考方向

### 证据一致性
solution.md 的最终答案与 gen.py/solve.py 的 exec 输出是否一致？
题干设问指向的量与 solution 给出的答案是否对齐？

### 设计卡对齐
design_card 的 expected_reasoning_actions 是否在 solution 中体现？
terminology constraints 是否被题干满足？
hard_constraints 是否在最终题目中真正实现？

### 交付完整性
question.md 是否完整（题干+设问+选项/子问）？
solution.md 是否完整（求解过程+最终答案）？
选择题是否有 A/B/C/D 选项？综合题是否有子问链？

## 路由判定

- **pass**：质量合格，可交付。写 final_review.md + final.md。
- **needs_fix**：有表述/格式/一致性小问题。给修改建议，design 调整一次后直接输出。
- **question_error**：题目结构有严重问题（如缺子问、考点偏离）。回 design 重做。
- **solution_error**：求解有严重问题（如答案错误、缺求解过程）。回 design_solve 重做。

> needs_fix 是轻量修改（表述/格式），只调一次就输出。
> question_error/solution_error 是严重问题，需要回退重做。

## 输出

写 final_review.md（审核结论 + 路由判定）。
当 pass 时，同时写 final.md（最终交付文档：question + solution 组装）。

## 红线

- 不得脑内算答案
- 不得因选择题有选项值就打回（这是正常交付状态）
- needs_fix 只用于表述/格式小问题，不用于结构性问题
