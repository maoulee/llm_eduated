## status
draft

## blueprint_contract
- slot_id: DS-5-树与二叉树-二叉树带权路径长度
- question_type: single_choice
- score: 2
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度
- examination_mode: 给定权值集合计算哈夫曼树WPL
- k_target: K1=2,K2=3,K3=3,K4=2,K5=2
- difficulty_level: 3
- should_be: 考察WPL定义理解与哈夫曼树构造计算
- should_be: 计算量适中，中等难度
- should_be: 叶子节点数量4-5个
- should_be: 权值为正整数，有明显差异
- should_be: WPL结果在[50, 300]范围内
- should_be: 权值集合应能构造唯一哈夫曼树，或明确权值相等时的合并规则
- should_not_be: 权值全同
- should_not_be: 路径长度计算为层数而非层数-1
- should_not_be: WPL包含内部节点
- hard_constraints: 选择题4个选项，干扰策略为计算错误型/构造错误型/概念混淆型

## route
- question_form: single_choice
- question_type: computational
- requires_parameter_verification: true
- requires_solver: true
- requires_code: true

## core_knowledge_intent
- must_test: 哈夫曼树构造算法（贪心合并最小两权值）
- must_test: 带权路径长度WPL定义（仅叶子节点，路径长度=层数-1）
- must_test: 哈夫曼树WPL计算方法（自底向上或自顶向下累加）
- must_not_shift_to: 普通二叉树的WPL计算（非哈夫曼树）
- must_not_shift_to: 哈夫曼编码长度计算（混淆编码长度与WPL）
- coverage_success_criteria: 学生能正确执行哈夫曼合并流程并准确计算WPL
- coverage_success_criteria: 学生能区分WPL仅含叶子节点、路径长度从根到叶的边数

## design_rationale
本题考察哈夫曼树WPL计算这一408经典考点，选择"给定权值集合求WPL"而非"给定树结构求WPL"，是因为前者要求学生完整执行哈夫曼构造流程（反复选取最小两权值合并），而非仅做简单的加权求和。这种设问方式能有效区分两类学生：一类能完整走完贪心合并流程、理解每次合并对最终WPL的贡献，另一类只记得"把权值乘路径长度再求和"但无法正确构造哈夫曼树。K-雷达形状（K2=3,K3=3较高）反映本题需要中等记忆（哈夫曼算法步骤）和中等理解（WPL定义与合并逻辑），计算量适中（4-5个权值，2-3轮合并），避免纯机械计算或过度复杂化。选择题形式配合三种干扰策略（计算错误/构造错误/概念混淆），能精准捕捉学生在路径长度定义、合并顺序、WPL范围上的典型认知偏差。

## expected_reasoning_actions
- 将给定权值集合按从小到大排序
- 选取当前最小两个权值，构造新内部节点，权值为两者之和
- 将新权值放回集合，重复选取最小两个权值合并，直至只剩一个权值
- 根据构造出的哈夫曼树，确定每个叶子节点的路径长度（根到该叶子的边数）
- 将每个叶子节点的权值乘以其路径长度，求和得到WPL
- 验证WPL计算仅包含叶子节点，不包含内部节点

## question_structure_plan
- stem_style: 给定一个权值集合，要求计算对应哈夫曼树的带权路径长度WPL
- asking_method: 直接问WPL的数值
- option_architecture:
  - correct: 正确执行哈夫曼合并流程后计算的WPL值
  - distractor_1（计算错误型）: 路径长度误算为层数（多算1）导致的偏大结果
  - distractor_2（构造错误型）: 哈夫曼合并顺序错误（未选最小两权值）导致的错误WPL
  - distractor_3（概念混淆型）: WPL计算中错误纳入内部节点权值，或混淆WPL与树的其他参数（如总结点数、树高）

## parameter_plan
- parameter_slots:
  - name: leaf_count
    role: 叶子节点数量
    candidate_range: [4, 5]
    used_by: 权值集合生成、WPL计算
  - name: weight_values
    role: 叶子节点权值集合
    candidate_range: 每个权值 ∈ [1, 50] 的正整数，应有明显差异，可重复但不全同
    used_by: 哈夫曼树构造、WPL计算
  - name: wpl_result
    role: 正确WPL值
    candidate_range: [50, 300]
    used_by: 正确选项、干扰项生成基准
- validation_targets:
  - 权值集合能构造唯一哈夫曼树，或权值相等时有明确合并规则
  - WPL计算结果在[50, 300]范围内
  - 三个干扰项与正确答案数值不同且互不相同
  - 干扰项1（路径长度+1）≠ 干扰项2（合并顺序错误）≠ 干扰项3（概念混淆）
- adjustment_priority:
  - 优先调整权值集合使WPL落在目标范围
  - 其次确保三个干扰项数值互异
  - 最后微调权值使合并流程有2-3轮

## terminology_and_expression_constraints
- required_terms: 哈夫曼树、带权路径长度、WPL、叶子节点、路径长度
- required_qualifiers: 路径长度指从根结点到该结点的路径上的分支数（边数）
- required_qualifiers: WPL仅计算叶子节点的带权路径长度之和
- avoid_phrases: 路径长度=层数
- avoid_phrases: WPL包含所有节点
- standard_rewrites:
  - bad: 求该哈夫曼树的路径长度
    good: 求该哈夫曼树的带权路径长度WPL
  - bad: 路径长度为从根到该结点的层数
    good: 路径长度为从根到该结点的分支数（边数）

## audit_focus
- final_review_must_check: WPL计算仅包含叶子节点，不包含内部节点
- final_review_must_check: 路径长度定义为根到叶子的边数（层数-1）
- final_review_must_check: 哈夫曼合并流程每次选取最小两个权值
- final_review_must_check: 四个选项数值互不相同
- final_review_must_check: 正确答案在[50, 300]范围内
- solve_output_should_contain: 哈夫曼树构造的完整合并过程（每轮选取的权值、新权值）
- solve_output_should_contain: 每个叶子节点的路径长度和带权路径长度
- solve_output_should_contain: WPL的最终计算式与结果
- fail_if_missing: 缺少哈夫曼合并流程的逐步展示
- fail_if_missing: WPL计算包含内部节点
- fail_if_missing: 路径长度计算错误（用层数代替边数）