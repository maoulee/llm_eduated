# 题目审核技能

## 输出格式（必须严格遵循）

```markdown
## status
pass

## summary
（审核总结，1-2句话）

## corrections
无

## detailed_feedback
（逐项审核发现）

## quality_score
- knowledge: X/10
- difficulty_match: X/10
- condition_sufficiency: X/10
- expression_clarity: X/10
- option_quality: X/10

## improvement_suggestions
（即使 pass 也必须填写）
```

**status 必须是 `pass` 或 `needs_fix`**，写在 `## status` 下的第一行，不要用表格或加粗包裹。

## 审核流程

### Step 1: 知识点覆盖检查
- 列出规划中要求的所有知识点
- 逐一检查题目是否覆盖
- 标记遗漏和新增

### Step 2: K难度评估
- 根据K1-K5评分标准评估实际K值
- 与规划目标对比
- 差异>=2级标记 needs_fix

### Step 3: 条件充分性
- 列出题干所有给定条件
- 检查每个条件是否被子问题/选项使用
- 检查是否有缺失条件

### Step 4: 题干清晰度
- 是否有歧义表述
- 参数符号是否一致
- 隐含假设是否显式声明

### Step 5: 选项/子问题质量
- 选择题：4选项1正确，干扰项有效
- 综合题：编号连续，分值合理

## 判定规则
- 实质性问题（知识点遗漏、K偏差>=2、条件矛盾、选项不唯一）→ needs_fix
- 润色建议不算实质性问题 → pass
