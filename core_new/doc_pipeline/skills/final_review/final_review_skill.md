# 终审技能

## 输出格式（必须严格遵循）

```markdown
## status
pass

## summary
（审核总结）

## corrections
（仅 expression_fix 时写修正内容，否则写"无"）

## detailed_feedback
（逐项审核发现）

## quality_score
- overall: X/10
- knowledge: X/10
- self_consistency: X/10
- difficulty_match: X/10
- expression_precision: X/10

## improvement_suggestions
（即使 pass 也必须填写）

## routing_feedback
（仅 question_error / solution_error 时填写具体修正要求）
```

**status 必须是以下之一：`pass`、`expression_fix`、`question_error`、`solution_error`**，写在 `## status` 下的第一行，不要用表格或加粗包裹。

## 审核流程

### Step 1: 求解正确性验证
- 检查 solution.md 是否回答了 question.md 的每个子问题
- 数值题：可用 exec_python 独立重算验证
- 概念题：检查推理是否基于标准定义

### Step 2: 答案唯一性
- 题目条件是否足以推导唯一答案
- 是否存在合理但不同的解答路径导致不同答案

### Step 3: 条件利用率
- 列出题干中所有给定条件
- 逐一检查每个条件在求解中是否被使用
- 标记未使用条件和缺失条件

### Step 4: 答案自洽性
- 推理链无跳步、无循环论证
- 中间结果与最终答案一致
- 单位换算链正确

### Step 5: 蓝图匹配
- 知识点覆盖 vs 规划
- K难度实际评估 vs 目标
- 差异>=2级需标记

## 路由判定规则

### pass（通过）
- 求解正确
- 条件利用充分
- 答案自洽
- 可有微小瑕疵但不影响正确性

### expression_fix（就地修正）
**严格条件**：
- 仅措辞/格式问题
- 不涉及参数值修改
- 不涉及逻辑变更
- 不影响答案正确性

**操作**：
- 用 edit_file 直接修改
- 不需要回退到其他 Agent

### question_error（题目错误）
**触发条件**：
- 参数矛盾（两个条件互相冲突）
- 条件缺失（无法推导出唯一答案）
- 条件冗余（存在无用条件）
- 知识点错误（考察内容与规划不符）
- 题干歧义（存在多种合理解读）

**操作**：输出 review_feedback.md，回退到 Question Agent

### solution_error（求解错误）
**触发条件**：
- 计算错误（数值不对）
- 推理错误（逻辑不正确）
- 遗漏子问题（未覆盖所有子问题）
- 硬编码痕迹（结果非推导得出）

**操作**：输出 review_feedback.md，回退到 Solve Agent

## 就地修正操作指南

当判定为 expression_fix 时：
1. read_file 读取需要修正的文件
2. edit_file 进行最小修正（不改变参数值和逻辑）
3. 如涉及数值表述，用 exec_python 验证
4. write_file 输出 final_review.md
5. 组装 final.md

## 修复反馈格式

当判定为 question_error 或 solution_error 时，review_feedback.md 必须包含：

```markdown
## 错误定位
- 文件: question.md 或 solution.md
- 位置: 具体章节/子问题
- 错误类型: 参数矛盾/条件缺失/计算错误/推理错误

## 具体问题
1. （精确描述问题）
2. ...

## 修正建议
- （具体可操作的修正方向）
```
