# assembled.md — 机器契约

## meta
```yaml
slot_id: "DS_CHOICE_KMP_NEXT"
chapter: "数据结构-串"
question_type: "choice"
score: 2
knowledge_points:
  - "KMP算法"
  - "next数组计算"
  - "模式匹配"
```

## k_targets
```yaml
K1_knowledge_breadth: 2
K2_computation_complexity: 3
K3_trap_depth: 3
K4_cross_domain: 1
K5_comprehensive: 3
```

## examination_mode
```yaml
mode: "direct_calculation"
description: "给出模式串，要求计算next数组（或nextval数组）的值"
historical_reference: "KMP next数组计算为408高频考点"
```

## sub_questions
```yaml
# 选择题，无子问题
count: 0
```

## parameter_constraints
```yaml
pattern_string:
  length_range: [6, 10]
  charset: "lowercase_letters"
  structure_requirements:
    - "must_contain_repeated_substring"
    - "at_least_one_prefix_suffix_match"
    - "avoid_all_identical_characters"

next_array_definition:
  specification_required: true
  note: "题干需明确next数组计算规则或采用教材标准定义"

options:
  count: 4
  correct_count: 1
  distractor_strategies:
    - "index_offset_error"
    - "nextval_confusion"
    - "prefix_suffix_length_error"
```

## design_card
```yaml
design_notes: "考察KMP算法next数组的手动计算能力"
expected_actions:
  - "理解next数组定义"
  - "逐位推导next值"
  - "识别前后缀相等关系"
common_pitfalls:
  - "下标从0还是从1开始的定义差异"
  - "next与nextval混淆"
  - "前后缀长度计算off-by-one"
```

## teacher_annotations
```yaml
# 留空，供教师审阅时填写
difficulty_assessment: ""
parameter_suggestions: ""
other_comments: ""
```

## validation_checklist
```yaml
- k_targets_complete: true
- examination_mode_justified: true
- parameter_constraints_ranges_not_values: true
- sub_questions_complete: true
- teacher_annotations_reserved: true
```
