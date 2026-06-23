## status
draft

## blueprint_contract
- slot_id: （未指定）
- question_type: comprehensive
- score: 10-11（子问题1: 6-7分，子问题2: 3-4分）
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树遍历序列还原
- examination_mode: 给定双序列还原 + 属性推导
- k_target: K1=3,K2=3,K3=3,K4=2,K5=3
- difficulty_level: 3
- should_be:
  - 节点数 n: 6 ≤ n ≤ 10
  - 遍历序列组合: [前序, 中序] 或 [后序, 中序]
  - 节点值: n个互不相同的字符或数字
  - 树结构: 左右子树均非空
  - 高度 2 ≤ h ≤ n-1
  - 至少一个度为2的节点
  - 序列一致性: 两种遍历序列必须对应同一棵二叉树
  - 子问题串行依赖（第2问依赖第1问结果）
- should_not_be:
  - 前序+后序组合（不能唯一确定二叉树）
  - 左右子树存在空子树的情况
  - 节点值重复
- hard_constraints:
  - sub_question_count: 2
  - dependency: 串行
  - condition_count: 2

## route
- question_form: comprehensive
- question_type: mixed
- requires_parameter_verification: true
- requires_solver: true
- requires_code: false

## core_knowledge_intent
- must_test:
  - 由前序（或后序）+ 中序遍历序列唯一还原二叉树结构的递归分割能力
  - 层序遍历的队列执行顺序理解，或树属性（高度/度为2节点数/叶子数）的计算
- must_not_shift_to:
  - 仅考察遍历序列之间的直接转换（如已知前序求后序）而不要求还原树结构
  - 前序+后序组合（无法唯一确定二叉树）
- coverage_success_criteria:
  - 第1问要求完整还原二叉树结构（画图或写出各节点父子关系），体现递归分割过程
  - 第2问基于还原结果计算层序遍历序列或树属性，验证还原正确性

## expected_reasoning_actions
- 从前序序列首元素（或后序序列末元素）确定根节点
- 在中序序列中定位根节点位置，分割出左子树中序序列和右子树中序序列
- 根据左右子树节点数量，在前序（或后序）序列中分割出左子树前序（后序）序列和右子树前序（后序）序列
- 对左右子树递归执行上述分割过程，直至子树为空或仅含单节点
- 根据还原的树结构，按层序遍历规则（队列FIFO）逐层输出节点，或计算树的高度/度为2的节点数/叶子节点数

## question_structure_plan
- shared_context: 给出某二叉树的两种遍历序列（前序+中序 或 后序+中序），节点数为6-10个互不相同的字符或数字
- sub_question_chain:
  - 子问题1（6-7分）：根据给定的两种遍历序列，还原并画出该二叉树的结构（或写出各节点的父子关系）
  - 子问题2（3-4分）：基于还原的二叉树，写出其层序遍历序列（或计算树的高度/度为2的节点数/叶子节点数）
- dependency_pattern: 串行——子问题2必须依赖子问题1还原出的树结构
- distractor_strategy（干扰认知路径）:
  - 根节点位置混淆：将前序首元素误认为中序首元素，或后序末元素定位错误
  - 递归边界错误：分割左右子树时节点数量计算偏差（off-by-one）
  - 层序遍历队列顺序错误：同层节点左右顺序颠倒，或跨层节点顺序混乱

## parameter_plan
- parameter_slots:
  - n（节点数）: role=控制题目规模, candidate_range=[6, 7, 8, 9, 10], used_by=遍历序列长度、树结构复杂度
  - traversal_pair（遍历序列组合）: role=决定还原方法, candidate_range=[(前序, 中序), (后序, 中序)], used_by=题干给出的序列类型
  - node_values（节点值集合）: role=遍历序列内容, candidate_range=n个互不相同的字符（如A-J）或数字（如1-10）, used_by=两种遍历序列
  - tree_structure（目标树结构）: role=生成遍历序列的基准, candidate_range=左右子树均非空、高度2≤h≤n-1、至少一个度为2的节点, used_by=生成前序/中序/后序序列
- validation_targets:
  - 两种遍历序列必须对应同一棵二叉树（序列一致性）
  - 还原出的树结构左右子树均非空
  - 树高度满足 2 ≤ h ≤ n-1
  - 至少存在一个度为2的节点
  - 节点值互不重复
- adjustment_priority:
  - 优先调整 tree_structure 确保满足结构约束
  - 其次调整 n 在[6,10]范围内使题目难度适中
  - 最后调整 node_values 使序列表达清晰

## terminology_and_expression_constraints
- required_terms:
  - 前序遍历（先序遍历）、中序遍历、后序遍历、层序遍历
  - 根节点、左子树、右子树、叶子节点、度为2的节点
- required_qualifiers:
  - 必须说明"前序+中序"或"后序+中序"可唯一确定二叉树
  - 层序遍历需说明"从上到下、从左到右"的访问顺序
- avoid_phrases:
  - "先序"与"前序"混用——统一使用"前序遍历"
  - "层次遍历"——应使用"层序遍历"
  - "深度"——应使用"高度"（树的高度定义）
- standard_rewrites:
  - bad: "请根据先序和中序序列画出二叉树" →I have to give the solution based on the reasoning directly now.</think>

## audit_focus
- final_review_must_check:
  - 两种遍历序列是否严格对应同一棵二叉树（序列一致性验证）
  - 还原的树结构是否满足：左右子树均非空、高度2≤h≤n-1、至少一个度为2的节点
  - 节点数n是否在[6,10]范围内
  - 子问题2是否明确依赖子问题1的还原结果（串行依赖）
  - 遍历序列组合是否为[前序,中序]或[后序,中序]（排除前序+后序）
- solve_output_should_contain:
  - 完整的递归分割过程（根节点定位→中序分割→子序列分割→递归）
  - 还原出的二叉树结构（图形或父子关系描述）
  - 层序遍历序列（或树属性计算结果）及计算过程
  - 参数自洽性验证（两种序列对应同一棵树）
- fail_if_missing:
  - 缺少递归分割的关键步骤说明
  - 两种遍历序列无法还原出唯一二叉树
  - 树结构违反约束（空子树/高度越界/无数为2节点）
  - 子问题2未依赖子问题1结果