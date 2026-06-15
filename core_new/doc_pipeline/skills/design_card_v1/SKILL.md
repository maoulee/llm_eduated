# 骨架设计技能

## 目标
设计题目骨架：考什么、怎么分问、每问考察什么。不设计具体参数/数值。

## 必须包含 7 个 section
1. status
2. blueprint_contract
3. core_knowledge_intent
4. design_rationale（含考点融合意图，如有）
5. question_structure_plan（经验驱动的子问链）
6. terminology_and_expression_constraints
7. audit_focus

## 已移除的 section（不再需要）
- ~~route~~：系统根据 complexity 判断，不是骨架的事
- ~~expected_reasoning_actions~~：解题步骤是下游 solve 的事
- ~~parameter_plan~~：具体参数是下游 gen.py 的事

## blueprint_contract
从蓝图原样摘取。不得修改 should_be / should_not_be / K目标 / 难度。

## core_knowledge_intent
- must_test：本题必须考什么（2-3项）
- must_not_shift_to：不允许偏移到什么
- coverage_success_criteria：覆盖成功的标准

## design_rationale（设计理念 + 考点融合）

回答：**"为什么这样考？"**

写清楚：
- 本题考察意图：为什么选这个考点组合、这种设问方式
- 区分什么样掌握程度的学生
- 为什么这个难度合适

**考点融合**（仅 K3-K4 高难度，可选）：
- 同一知识点的不同考察项融合（如 AVL 既考旋转辨析又考平衡因子计算）
- 不是跨考点融合，不是强行要求
- 在这里决定，写入此段。下游看到多个考察项直接实现

## question_structure_plan（经验驱动的子问链）

**子问数量和每问考什么 = 经验驱动**：
- 如果 assembled.md 有往年真题经验/模式概览 → 从中提取子问模式
- 如果没有经验 → 基于考察形式给合理默认（综合题 2-3 问，串行依赖）

格式：
```
- 子问1：考[考察点]（基础层，如"插入后的旋转类型判断"）
- 子问2：基于子问1的结果，考[考察点]（进阶层，如"第二次插入的不同类型旋转"）
- 子问3（可选）：汇总/分析（区分度层）
- dependency_pattern：串行依赖
```

**只写"考什么"，不写"怎么算"。不写具体数值/节点/参数。**

## 通用干扰模式库（供 audit_focus 参考）

### 计算型干扰
- 单位换算陷阱、符号错误、偏移错误(off-by-one)、中间值、倒置

### 概念型干扰
- 概念混淆、过度推断、条件遗漏、张冠李戴

### 组合判断型干扰
- I/II/III 各代表独立命题，干扰项是"真+假"混合组合

## 教师说明与排除项
- teacher_annotation 必须在 blueprint_contract 或 audit_focus 中体现
- excluded.modes / excluded.knowledge 不得进入 must_test

## 关键约束
- 不得出现具体数值/答案/最终计算结果
- question_structure_plan 只写考察方向，不写解题步骤
- 不设计具体参数（节点值/插入序列/资源矩阵）
- 当往年经验与本次要求冲突时，以本次出题要求为最高优先级
