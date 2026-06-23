# design_card Schema v1

> Phase 0 产物。`design_card.md` 是 question writer 前的设计意图卡，不是题目、不是答案、不是求解过程。

## 设计目标

1. 把单题蓝图转成可执行的出题意图
2. 降低 question_sc / question_comp 的输入复杂度
3. 给 final_review 提供可对照的设计依据
4. 帮助定位失败原因：设计错 / 题干写偏 / 参数没支撑 / solver 错

---

## 文件整体格式

```markdown
# design_card

## status
draft

## blueprint_contract
...

## route
...

## core_knowledge_intent
...

## expected_reasoning_actions
...

## question_structure_plan
...

## parameter_plan
...

## terminology_and_expression_constraints
...

## audit_focus
...
```

共 9 个 section，全部为 `##` 级别 heading。

---

## 字段定义

### 1. `status`

必填。只允许 `draft`。

禁止：pass / needs_fix / final / solved。design_card 是设计中间产物，不承担审核状态。

### 2. `blueprint_contract`

无损摘取单题蓝图中的硬约束。

```markdown
## blueprint_contract
- slot_id: Qxx
- question_type: single_choice / comprehensive
- score: ...
- target_subject: ...
- target_family: ...
- primary_target_name: ...
- examination_mode: ...
- k_target: ...
- difficulty_level: ...
- should_be:
  - ...
- should_not_be:
  - ...
- hard_constraints:
  - ...
```

**允许**：从单题蓝图原样摘取题型、分值、知识点、考察模式、K难度、should_be、should_not_be、硬约束。

**禁止**：自行新增蓝图没有的核心知识点；自行降低或提高 K 难度；把 should_not_be 改写成可接受项；删掉蓝图中的硬约束。

### 3. `route`

决定后续走概念题轻路径，还是参数验证 + solver 路径。

```markdown
## route
- question_form: single_choice / comprehensive
- question_type: conceptual / computational / mixed
- requires_parameter_verification: true / false
- requires_solver: true / false
- requires_code: true / false
```

| question_type | parameter_verification | solver | code |
|---|---|---|---|
| conceptual | false | false | false |
| computational | true | true | true |
| mixed | true | true | true |

**禁止**：把明显计算题标成 conceptual；把纯概念题标成 requires_code=true。

### 4. `core_knowledge_intent`

说明这题必须真正考到什么，而不是只出现关键词。

```markdown
## core_knowledge_intent
- must_test:
  - ...
- must_not_shift_to:
  - ...
- coverage_success_criteria:
  - ...
```

**允许**：写知识点覆盖标准（如"必须通过计算 Cache 块内偏移位、组号位、标记位体现地址字段划分"）。

**禁止**：写具体答案、写具体数值结果、写完整解题过程。

### 5. `expected_reasoning_actions`

最关键字段。描述后续 solver 应该发生的"解题动作"，不写答案。

```markdown
## expected_reasoning_actions
- action_1: ...
- action_2: ...
- action_3: ...
```

**允许**：只写动作。如"由块大小推出块内偏移位数"、"定位首个失衡结点"。

**禁止**：写具体数值（offset=6）、写答案（正确答案是B）、写最终结果。

**约束**：此字段不能泄露给 solver。solver 保持独立性。

### 6. `question_structure_plan`

给 question writer 一个窄输入，告诉它怎么组织题目。

**选择题格式**：
```markdown
## question_structure_plan
- stem_style: 简洁题干 / 场景计算 / 命题判断 / 组合判断
- option_architecture:
  - correct_option_role: ...
  - distractor_1_role: ...
  - distractor_2_role: ...
  - distractor_3_role: ...
- asking_method: ...
```

**综合题格式**：
```markdown
## question_structure_plan
- shared_context: ...
- sub_question_chain:
  - q1_role: 基础参数计算 / 机制判断
  - q2_role: 过程模拟 / 状态跟踪
  - q3_role: 结果分析 / 边界讨论
- dependency_pattern:
  - q2 depends on q1
  - q3 depends on q2
```

**禁止**：写完整题干、写最终选项文本、写答案。

### 7. `parameter_plan`

只描述参数槽位、候选范围、验证目标。不做参数推导，不写验证代码。

```markdown
## parameter_plan
- parameter_slots:
  - name: ...
    role: ...
    candidate_range: ...
    used_by: ...
- validation_targets:
  - ...
- adjustment_priority:
  - ...
```

**允许**：写候选范围（"页大小候选 1KB / 2KB / 4KB"）、写验证目标（"需验证组数为 2 的幂"）。

**禁止**：写 Python 代码、写 assert 模板、证明参数自洽、写最终计算结果。

### 8. `terminology_and_expression_constraints`

提前防止概念误导。

```markdown
## terminology_and_expression_constraints
- required_terms:
  - ...
- required_qualifiers:
  - ...
- avoid_phrases:
  - ...
- standard_rewrites:
  - bad: ...
    good: ...
```

**禁止**：做语言润色长文；引入和蓝图无关的新概念。

### 9. `audit_focus`

给 final_review 用，让它知道最终必须查什么。

```markdown
## audit_focus
- final_review_must_check:
  - ...
- solve_output_should_contain:
  - ...
- fail_if_missing:
  - ...
```

**允许**：写可检查证据（如"solve_output 应体现失衡结点定位、旋转类型判断、旋转后树结构"）。

**禁止**：写具体答案；写"只要选 B 即通过"这种答案泄露。

---

## 数据流约束

```
assembled.md → question_design → design_card.md
design_card.md → question_writer (question_sc / question_comp)
question_writer → parameter_verify
question_writer/parameter_verify → solver (solver 只看 question.md)
design_card + question + solve_output → final_review
```

关键约束：
- solver **不读** design_card
- final_review **必须读** design_card
- design_card 是内部 debug artifact，不进入最终卷面

---

## 实现阶段

| Phase | 内容 | 依赖 |
|---|---|---|
| Phase 0 | 冻结 schema + 示例 + 校验器 | 无 |
| Phase 1 | 新增 question_design agent (feature flag) | Phase 0 |
| Phase 2 | 缩窄 question writer 输入为 design_card | Phase 1 |
| Phase 3 | StemBlueprintGate / SolverVerify 对齐设计卡 | Phase 2 |
| Phase 4 | final_review 增强证据链（4维对齐） | Phase 3 |
| Phase 5 | compose / export 集成 | Phase 4 |
