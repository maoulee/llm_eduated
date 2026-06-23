## status
draft

## blueprint_contract
slot_id: DS-5-综合题
question_type: comprehensive
score: 12-15
target_subject: 数据结构
target_family: DS-5 > 树与二叉树
primary_target_name: 二叉树遍历序列还原
examination_mode: 经典还原模式（给定两种遍历序列还原二叉树）
k_target: K1=3,K2=3,K3=2,K4=3,K5=3
difficulty_level: 3
should_be: 给定两种遍历序列（必须包含中序）还原二叉树
should_be: 子问题2-3问，串行依赖
should_be: 节点数5-10，树高3-4
should_be: 两种序列对应同一棵树，长度均为n
should_not_be: 不包含中序的序列对（如前序+后序无法唯一还原）
should_not_be: 节点值重复
should_not_be: 树高超出[3,4]范围
hard_constraints: 必须包含中序遍历；节点值互不相同；两种序列长度一致；还原后树高在[3,4]

## route
question_form: comprehensive
question_type: mixed
requires_parameter_verification: true
requires_solver: true
requires_code: false

## core_knowledge_intent
must_test:
- 由前序/后序确定根节点，由中序划分左右子树的递归还原方法
- 二叉树深度与叶子节点的递归定义与计算方法
- 遍历序列唯一性条件（中序的必要性）

must_not_shift_to:
- 仅考查遍历序列的机械书写而不考查还原过程
- 堆/优先队列等其他树结构的性质

coverage_success_criteria:
- solver能根据两种遍历序列完整还原二叉树结构
- solver能正确计算树高和叶子节点数，且与还原结果一致

## expected_reasoning_actions
- 从前序序列首元素（或后序序列末元素）确定根节点
- 在中序序列中定位根节点，划分左子树和右子树的节点集合
- 递归地对左右子树重复上述过程，直至所有节点定位完成
- 根据还原的树结构，递归计算每个子树的深度
- 遍历还原后的树，统计度为0的节点（叶子节点）数量
- 分析缺少中序遍历时，根节点无法确定左右子树边界，导致还原不唯一

## question_structure_plan
shared_context: 给定某二叉树的前序遍历序列和中序遍历序列（或后序+中序），节点数为n（5≤n≤10），节点值为互不相同的字符或数字
sub_question_chain:
  - Q1: 还原二叉树结构或求第三种遍历序列（计算/还原，5-6分）
  - Q2: 求该二叉树的深度和叶子节点数（计算/分析，4-5分）
  - Q3: 分析仅凭前序和后序序列能否唯一确定该二叉树，说明理由（分析，3-4分，可选）
dependency_pattern: 串行（Q2依赖Q1还原的树结构；Q3可独立作答但建议结合Q1结果）
distractor_strategy:
  - 单位/概念混淆：混淆前序/中序/后序的根节点位置规则
  - 偏移错误：左右子树边界划分时多算或少算一个节点（off-by-one）
  - 中间值：将某层子树的深度当作整树深度

## parameter_plan
parameter_slots:
  - name: n (节点数)
    role: 控制题目规模
    candidate_range: [5, 10]
    used_by: 遍历序列长度、树结构复杂度
  - name: h (树高)
    role: 控制递归深度
    candidate_range: [3, 4]
    used_by: Q2深度计算验证
  - name: traversal_pair (遍历序列对)
    role: 确定还原方式
    candidate_range: [前序+中序, 后序+中序]
    used_by: Q1还原过程
  - name: node_values (节点值集合)
    role: 遍历序列内容
    candidate_range: 互不相同的字符或数字，长度为n
    used_by: 所有遍历序列

validation_targets:
  - 两种遍历序列长度均为n
  - 两种序列包含相同的n个节点值
  - 还原后的二叉树高度在[3,4]范围内
  - Q1还原结果与Q2计算的深度、叶子数一致
  - Q3分析结论正确（前序+后序无法唯一还原）

adjustment_priority:
  1. 确保两种序列对应同一棵树
  2. 确保树高在[3,4]
  3. 确保节点值互不相同

## terminology_and_expression_constraints
required_terms:
- 前序遍历（先序遍历）
- 中序遍历
- 后序遍历
- 根节点
- 左子树 / 右子树
- 递归
- 叶子节点（度为0的节点）
- 树的深度（高度）

required_qualifiers:
- 必须说明"中序遍历用于划分左右子树"
- 必须说明"前序首元素/后序末元素为根节点"
- 求深度时需说明"递归定义：max(左子树深度, 右子树深度) + 1"

avoid_phrases:
- "前序+后序可以唯一确定二叉树"（错误表述）
- "中序遍历确定根节点"（错误，中序用于划分左右子树）
- 混淆"深度"和"高度"（考研语境下通常等价，但需统一用词）

standard_rewrites:
  - bad: "根据前序和中序写出后序"
    good: "根据前序遍历序列和中序遍历序列还原二叉树，并写出后序遍历序列"
  - bad: "这棵树有3层"
    good: "该二叉树的深度为3"
  - bad: "前序和后序也能还原"
    good: "仅凭前序和后序遍历序列无法唯一确定二叉树结构，因为无法确定左右子树的边界"

## audit_focus
final_review_must_check:
- 两种遍历序列是否对应同一棵二叉树
- 还原后的树高是否在[3,4]范围内
- Q1、Q2、Q3分值分配是否合理（总计12-15分）
- Q3是否考查了中序遍历的必要性这一核心概念
- 节点值是否互不相同

solve_output_should_contain:
- 完整的二叉树还原过程（递归步骤）
- 还原后的树结构（可用图形或括号表示法）
- Q2中深度和叶子节点数的计算过程
- Q3中关于唯一性条件的分析说明
- 参数自洽性验证（两种序列长度一致、节点集合一致）

fail_if_missing:
- 缺少中序遍历的序列对
- 两种序列长度不一致或节点集合不一致
- 还原后树高超出[3,4]范围
- Q2结果与Q1还原的树结构矛盾
- Q3未涉及"中序遍历的必要性"这一核心考点
