## status
draft

## blueprint_contract
- slot_id: (未指定)
- question_type: comprehensive
- score: 10 (q1≈4 + q2≈3 + q3≈3)
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树遍历序列还原
- examination_mode: 遍历序列还原 + 性质分析
- k_target: K1=3,K2=3,K3=2,K4=3,K5=3
- difficulty_level: 3
- should_be:
  - 节点数 n 在 [6, 10] 范围内
  - 树高度 h 在 [3, 5] 范围内
  - 叶子节点数 2-4 个
  - 度为1的节点数 1-3 个
  - 左右子树有一定不对称性
  - 节点标识使用大写字母 A-Z 或数字 1-9，所有节点值互不相同
  - 前序序列和中序序列必须来自同一棵满足约束的二叉树
- should_not_be:
  - 不能是退化链
  - 不能是完全二叉树或满二叉树
- hard_constraints:
  - 序列一致性：前序序列和中序序列必须来自同一棵二叉树
  - 子问题依赖：q2 和 q3 均依赖 q1 的还原结果
  - 条件数量：2（前序遍历序列、中序遍历序列）

## route
- question_form: comprehensive
- question_type: mixed
- requires_parameter_verification: true
- requires_solver: true
- requires_code: false

## core_knowledge_intent
- must_test:
  - 根据前序遍历序列和中序遍历序列还原二叉树结构
  - 根据还原的二叉树写出后序遍历序列
  - 统计二叉树的高度、叶子节点数、度为1的节点数
- must_not_shift_to:
  - 仅使用一种遍历序列还原二叉树（必须同时使用前序和中序）
  - 层序遍历（除非题目明确要求，否则不考察）
- coverage_success_criteria:
  - 能正确从前序和中序序列递归还原出唯一的二叉树结构
  - 能基于还原的树结构正确计算后序序列和各项树性质

## expected_reasoning_actions
- 从前序遍历序列的第一个元素确定整棵树的根节点
- 在中序遍历序列中定位根节点位置，据此划分左子树和右子树的中序序列
- 根据左子树节点数量，在前序序列中划分左子树和右子树的前序序列
- 递归地对左子树和右子树执行相同的还原过程
- 基于还原完成的二叉树结构，按"左-右-根"顺序写出后序遍历序列
- 通过遍历或递归方式统计树的高度（根节点到最远叶子节点的路径长度）
- 识别并计数叶子节点（左右子树均为空的节点）
- 识别并计数度为1的节点（仅有一个非空子树的节点）

## question_structure_plan
- shared_context: 题干给出同一棵二叉树的前序遍历序列和中序遍历序列，要求基于这两个序列完成后续子问题
- sub_question_chain:
  - q1: 根据给定的前序遍历序列和中序遍历序列，还原并画出该二叉树的结构（分析/构造，≈4分）
  - q2: 写出该二叉树的后序遍历序列（计算，≈3分）
  - q3: 计算该二叉树的高度、叶子节点个数、度为1的节点个数（计算/分析，≈3分）
- dependency_pattern: serial（q2 和 q3 均依赖 q1 的还原结果）
- distractor_strategies:
  - 概念混淆：混淆前序和中序的根节点定位规则（如误将中序第一个元素当作根）
  - 偏移错误：递归划分边界时 off-by-one 错误，导致子树节点分配错误
  - 统计遗漏：统计树性质时漏数叶子节点或重复计数度为1的节点

## parameter_plan
- parameter_slots:
  - node_count: 节点总数，候选范围 [6, 10]，用于确定树的规模
  - tree_height: 树高度，候选范围 [3, 5]，需满足 h ≤ n
  - leaf_count: 叶子节点数，候选范围 [2, 4]
  - degree1_count: 度为1的节点数，候选范围 [1, 3]
  - preorder_sequence: 前序遍历序列，由构造的树生成，用于题干条件
  - inorder_sequence: 中序遍历序列，由构造的树生成，用于题干条件
  - node_labels: 节点标识符，候选为大写字母 A-Z 或数字 1-9，所有值互不相同
- validation_targets:
  - 前序序列和中序序列必须来自同一棵二叉树（序列一致性）
  - 构造的树不能是退化链、完全二叉树或满二叉树
  - 左右子树需有一定不对称性
  - 节点数、树高度、叶子节点数、度为1的节点数需满足参数范围约束
- adjustment_priority:
  - 第一优先级：节点数 n 和树高度 h（决定树的基本规模）
  - 第二优先级：树结构（确保不对称性、非退化、非完全/满二叉树）
  - 第三优先级：生成前序和中序序列（由树结构导出）

## terminology_and_expression_constraints
- required_terms:
  - 前序遍历（Preorder Traversal）
  - 中序遍历（Inorder Traversal）
  - 后序遍历（Postorder Traversal）
  - 根节点（Root Node）
  - 左子树 / 右子树（Left/Right Subtree）
  - 叶子节点（Leaf Node）
  - 度（Degree）
  - 树的高度（Height of Tree）
- required_qualifiers:
  - 必须明确是"二叉树"而非一般树
  - 必须说明节点值"互不相同"
  - 描述遍历序列时需标明是"前序"、"中序"或"后序"
- avoid_phrases:
  - "先序遍历"（应统一使用"前序遍历"）
  - "深度"（描述树时应使用"高度"）
  - 模糊表述如"这棵树"（应明确指代"该二叉树"）
- standard_rewrites:
  - bad: "先序序列" → good: "前序遍历序列"
  - bad: "树的深度" → good: "树的高度"
  - bad: "没有孩子的节点" → good: "叶子节点"
  - bad: "只有一个孩子的节点" → good: "度为1的节点"

## audit_focus
- final_review_must_check:
  - 前序序列和中序序列是否来自同一棵二叉树（序列一致性验证）
  - 构造的树是否满足所有结构约束（非退化链、非完全/满二叉树、左右子树不对称）
  - 节点数、树高度、叶子节点数、度为1的节点数是否在指定范围内
  - q2 和 q3 是否明确依赖 q1 的还原结果
  - 子问题分值分配是否合理（q1≈4, q2≈3, q3≈3）
- solve_output_should_contain:
  - 还原的二叉树结构（图形或文字描述）
  - 后序遍历序列的完整结果
  - 树高度、叶子节点数、度为1的节点数的具体数值
  - 还原过程的递归划分步骤说明
- fail_if_missing:
  - 前序序列和中序序列不一致（无法还原唯一二叉树）
  - 树结构违反 should_not_be 约束（退化链、完全二叉树、满二叉树）
  - 参数超出指定范围（节点数、树高度、叶子节点数、度为1的节点数）
  - 子问题之间缺少明确的依赖关系说明
  - 节点标识符有重复值
