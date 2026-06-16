## status
draft

## blueprint_contract
- slot_id: (未指定)
- question_type: comprehensive
- score: 10
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树遍历序列还原
- examination_mode: 序列还原+性质分析
- k_target: K1=3,K2=3,K3=2,K4=3,K5=3
- difficulty_level: 3
- should_be:
  - 节点总数 5 ≤ n ≤ 10，建议 7-8
  - 树高 2 ≤ h ≤ 4
  - 叶子节点数 ≥ 2
  - 度为2的节点数 ≥ 1
  - 给出的两种遍历序列必须能唯一确定二叉树
  - 节点标签使用连续字母（A-J）或连续数字（1-10）
  - 子问题3个：q1构造(4分)、q2计算(3分)、q3分析(3分)
  - q2和q3依赖q1，q2和q3并行
- should_not_be:
  - 节点数少于5或多于10
  - 给出的两种遍历序列不能唯一确定二叉树
  - 混淆前序/后序根节点位置
  - 中序序列错误划分左右子树
  - 忽略空子树
- hard_constraints:
  - 遍历序列类型：前序+中序 或 后序+中序（二选一）
  - 串行依赖：q1→{q2, q3}

## route
- question_form: comprehensive
- question_type: mixed
- requires_parameter_verification: true
- requires_solver: true
- requires_code: false

## core_knowledge_intent
- must_test:
  - 根据两种遍历序列（前序+中序 或 后序+中序）唯一还原二叉树结构
  - 基于还原的二叉树写出第三种遍历序列
  - 分析二叉树的结构性质（如树高、叶子节点数、度为2的节点数等）
- must_not_shift_to:
  - 堆（优先队列）的构建与调整
  - 哈夫曼树的构造
  - 线索二叉树的遍历
- coverage_success_criteria:
  - 两种遍历序列能唯一确定一棵二叉树，且还原过程清晰可追溯
  - 第三种遍历序列与还原的二叉树结构一致
  - 性质分析结果与还原的二叉树结构一致

## expected_reasoning_actions
- 从给定遍历序列中识别根节点位置（前序首元素或后序末元素）
- 利用中序序列以根节点为界划分左右子树
- 递归地对左右子树重复根节点定位与子树划分，直至还原完整二叉树
- 对还原的二叉树执行第三种遍历（前序/中序/后序/层序），按遍历规则依次访问节点
- 统计二叉树的结构性质（树高、叶子节点数、度为2的节点数等）
- 验证还原的二叉树与给定两种遍历序列的一致性

## question_structure_plan
- shared_context: 给出某二叉树的两种遍历序列（前序+中序 或 后序+中序），节点标签为连续字母或数字
- sub_question_chain:
  - q1（构造，4分）：根据给出的两种遍历序列还原二叉树结构（可画图或描述结构）
  - q2（计算，3分）：写出该二叉树的第三种遍历序列
  - q3（分析，3分）：分析该二叉树的某项结构性质（如树高、叶子节点数、度为2的节点数等）
- dependency_pattern: 串行依赖，q1为前置，q2和q3并行依赖q1
- distractor_strategies:
  - 混淆前序/后序根节点位置（将前序首元素误认为后序末元素，或反之）
  - 中序序列错误划分左右子树（根节点在中序中的位置定位错误导致左右子树划分错误）
  - 忽略空子树（还原时遗漏某个子树为空的情况，导致结构不完整）

## parameter_plan
- parameter_slots:
  - node_count: 节点总数，候选范围 7-8，用于确定遍历序列长度
  - tree_height: 树高，候选范围 2-4，用于验证二叉树结构
  - leaf_count: 叶子节点数，候选范围 ≥2，用于q3性质分析
  - degree2_count: 度为2的节点数，候选范围 ≥1，用于q3性质分析
  - traversal_pair: 遍历序列类型，候选值 {前序+中序, 后序+中序}，用于题干给出
  - node_labels: 节点标签，候选值 {连续字母A-J, 连续数字1-10}，用于题干和答案
  - third_traversal: 第三种遍历类型，候选值 {前序, 中序, 后序, 层序}（与题干给出的两种不同），用于q2
  - property_to_analyze: q3考查的性质类型，候选值 {树高, 叶子节点数, 度为2的节点数, 总结点数}，用于q3
- validation_targets:
  - 两种遍历序列必须能唯一确定一棵二叉树
  - 还原的二叉树节点数、树高、叶子节点数、度为2的节点数与参数一致
  - 第三种遍历序列与还原的二叉树结构一致
  - q3性质分析结果与还原的二叉树结构一致
- adjustment_priority:
  - 优先调整二叉树结构以满足节点数、树高、叶子节点数、度为2的节点数约束
  - 其次调整遍历序列以确保唯一确定性
  - 最后调整q3考查的性质类型以匹配二叉树结构

## terminology_and_expression_constraints
- required_terms:
  - 前序遍历（先序遍历）、中序遍历、后序遍历、层序遍历
  - 根节点、左子树、右子树、叶子节点（终端结点）
  - 度为2的节点、树高（深度）
- required_qualifiers:
  - 遍历序列必须明确标注类型（如"前序遍历序列为：..."）
  - 还原二叉树时需说明"唯一确定"
  - 性质分析需明确统计对象（如"叶子节点数为..."而非模糊表述）
- avoid_phrases:
  - "先根遍历"（应使用"前序遍历"或"先序遍历"）
  - "I have to give the solution based on the reasoning directly now.</think>

## audit_focus
- final_review_must_check:
  - 两种遍历序列能否唯一确定二叉树（前序+中序或后序+中序的组合）
  - 还原的二叉树结构是否与两种遍历序列一致
  - 第三种遍历序列是否与还原的二叉树结构一致
  - q3性质分析结果是否与还原的二叉树结构一致
  - 节点数是否在7-8范围内
  - 树高是否在2-4范围内
  - 叶子节点数是否≥2
  - 度为2的节点数是否≥1
  - 节点标签是否为连续字母或连续数字
  - 子问题分值分配是否为4+3+3=10
  - q2和q3是否依赖q1
- solve_output_should_contain:
  - 还原的二叉树结构（图形或文字描述）
  - 还原过程的中间步骤（根节点定位、左右子树划分）
  - 第三种遍历序列的完整结果
  - q3性质分析的计算过程和结果
  - 参数一致性验证（节点数、树高、叶子节点数、度为2的节点数）
- fail_if_missing:
  - 两种遍历序列不能唯一确定二叉树
  - 还原的二叉树与给定遍历序列不一致
  - 第三种遍历序列与还原的二叉树不一致
  - 性质分析结果与还原的二叉树不一致
  - 节点数、树高、叶子节点数、度为2的节点数不满足约束