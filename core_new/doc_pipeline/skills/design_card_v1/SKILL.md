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

## route 字段枚举值（必须使用英文原值，不加中文注释）

- question_form: 只能写 `single_choice` 或 `comprehensive`
- question_type: 只能写 `conceptual`、`computational` 或 `mixed`

错误示例：`选择题`、`综合应用题（共享题干）`、`mixed（概念+计算）`
正确示例：`single_choice`、`comprehensive`、`mixed`

## expected_reasoning_actions
- 只写解题动作。
- 不写具体数值答案。
- 不写正确选项。
- 不写最终树结构、最终地址字段数值等结果。
- 格式：每行以 `- ` 开头，或使用编号列表。

## parameter_plan
- 只写参数槽位、候选范围、验证目标。
- 不写 Python 代码。
- 不写 assert 模板。
- 不证明参数自洽。

## terminology_and_expression_constraints
- 写必须使用的标准术语。
- 写必须补充的限定条件。
- 写容易误导的表达及标准改写。

## 教师说明与排除项

- 若输入包含 teacher_annotation，必须在 blueprint_contract 或 audit_focus 中体现其约束
- excluded.modes / excluded.knowledge 不得进入 must_test、expected_reasoning_actions、parameter_plan
- candidate_pool_visible 只表示教师可见候选池，不表示本题需要覆盖
- active_selection 才是本题实际采用的模式和知识点
