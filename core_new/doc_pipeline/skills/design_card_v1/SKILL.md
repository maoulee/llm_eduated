# design_card_v1 技能

## 目标
生成符合 schema v1 的 design_card.md。

## 必须包含 9 个 section
1. status
2. blueprint_contract
3. route
4. core_knowledge_intent
5. expected_reasoning_actions
6. question_structure_plan
7. parameter_plan
8. terminology_and_expression_constraints
9. audit_focus

## expected_reasoning_actions
- 只写解题动作。
- 不写具体数值答案。
- 不写正确选项。
- 不写最终树结构、最终地址字段数值等结果。

## parameter_plan
- 只写参数槽位、候选范围、验证目标。
- 不写 Python 代码。
- 不写 assert 模板。
- 不证明参数自洽。

## terminology_and_expression_constraints
- 写必须使用的标准术语。
- 写必须补充的限定条件。
- 写容易误导的表达及标准改写。
