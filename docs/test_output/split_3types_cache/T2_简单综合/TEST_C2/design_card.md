# design_card.md

## status
draft

## blueprint_contract
- slot_id: (未指定)
- question_type: comprehensive
- score: 10
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树遍历序列还原
- examination_mode: 序列还原 → 性质求解
- k_target: K1=3,K2=4,K3=3,K4=4,K5=2
- difficulty_level: 3
- should_be:
  - 节点数 n 满足 6 ≤ n ≤ 10
  - 树深度 d 满足 3 ≤ d ≤ 4
  - 遍历序列组合为前序+中序或后序+中序
  - 两种遍历序列必须能唯一确定二叉树
  - 叶子节点数 ≥ 2
  - 至少一个节点有左右孩子
  - 序列元素互不相同
  - 两种遍历序列对应同一棵二叉树
  - 第2问依赖第1问还原结果
- should_not_be:
  - 不能是退化链（每个节点最多一个孩子）
  - 不能是完全二叉树
  - 不能使用无法唯一确定二叉树的序列组合（如前序+后序）
  - 序列元素不能重复
- hard_constraints:
  - 节点数 6 ≤ n ≤ 10，整数
  - 树深度 3 ≤ d ≤ 4
  - 两种遍历序列必须对应同一棵二叉树
  - 子问题串行依赖：第2问依赖第1问结果

## route
- question_form: comprehensive
- question_type: mixed
- requires_parameter_verification: true
- requires_solver: true
- requires_code: false

## core_knowledge_intent
- must_test:
  - 由前序/后序序列确定根节点，结合中序序列划分左右子树边界的递归还原方法
  - 二叉树遍历序列与树结构之间的对应关系（根节点位置、子树边界）
  - 基于还原的树结构求解叶子节点数、树深度等性质
- must_not_shift_to:
  - 仅考察"给两序求第三序"而不要求还原树结构
  - 退化为完全二叉树的数组表示或堆结构问题
- coverage_success_criteria:
  - solver 能从前序/后序定位根节点，利用中序划分左右子树，递归还原出完整二叉树结构
  - solver 能基于还原的树结构正确计算叶子节点数或树深度

## expected_reasoning_actions
- 从前序序列的第一个元素（或后序序列的最后一个元素）确定根节点
- 在中序序列中定位根节点位置，划分左子树和右子树的元素范围
- 根据左右子树元素个数，在前序/后序序列中切分出左右子树对应的子序列
- 对左右子树递归执行上述还原过程，直至所有子树还原完成
- 基于还原的二叉树结构，逐节点判断叶子节点（无左右孩子）并计数
- 基于还原的二叉树结构，计算树的最大深度（根到最远叶子节点的路径长度）

## question_structure_plan
- shared_context: 给出两种遍历序列（前序+中序 或 后序+中序），说明序列元素互不相同，且两种序列对应同一棵二叉树
- sub_question_chain:
  - 第1问（6分）：根据给定的两种遍历序列还原二叉树结构，要求给出树的结构表示（如括号表示法、层序序列或文字描述）
  - 第2问（4分）：基于第1问还原的二叉树，求解树的性质（如叶子节点数、树深度、某类节点计数等）
- dependency_pattern: 串行依赖——第2问的计算必须基于第1问还原的树结构
- distractor_strategy:
  - 干扰类型1（根节点位置混淆）：将前序首元素误认为中序首元素，或后序末元素定位错误
  - 干扰类型2（左右子树边界错误）：中序划分时左右子树元素范围切分错误，导致子树结构颠倒
  - 干扰类型3（性质计算偏差）：叶子节点计数遗漏/多计、深度计算 off-by-one、中间结果误作最终答案

## parameter_plan
- parameter_slots:
  - name: n (节点数)
    role: 控制题目规模，影响还原递归深度和计算复杂度
    candidate_range: 6 ~ 10（整数）
    used_by: 遍历序列长度、树结构构造
  - name: d (树深度)
    role: 控制树的高度，影响第2问深度计算
    candidate_range: 3 ~ 4
    used_by: 树结构构造、第2问答案
  - name: traversal_combo (遍历序列组合)
    role: 决定还原方法的入口（前序首元素 or 后序末元素）
    candidate_range: [前序+中序, 后序+中序]
    used_by: 题干序列给出、还原推理路径
  - name: leaf_count (叶子节点数)
    role: 第2问可能的求解目标之一
    candidate_range: ≥ 2
    used_by: 第2问答案
  - name: sequence_elements (序列元素)
    role: 遍历序列中的节点标识
    candidate_range: 互不相同的字符（如 A~J）或数字（如 1~10）
    used_by: 题干序列、还原过程
  - name: tree_structure (树结构)
    role: 隐含参数，由遍历序列唯一确定
    candidate_range: 满足约束的非退化、非完全二叉树
    used_by: 序列生成、答案验证
- validation_targets:
  - 两种遍历序列必须对应同一棵二叉树（一致性校验）
  - 节点数 n 在 [6, 10] 范围内
  - 树深度 d 在 [3, 4] 范围内
  - 树结构不是退化链（存在至少一个节点有左右孩子）
  - 树结构不是完全二叉树
  - 叶子节点数 ≥ 2
  - 第2问答案与还原树结构一致
- adjustment_priority:
  1. 节点数 n（优先确定，影响序列长度和递归深度）
  2. 树深度 d（与 n 配合确定树形态）
  3. 遍历序列组合（前序+中序 or 后序+中序）
  4. 树结构（由 n、d 和结构约束共同确定）
  5. 序列元素（最后分配，确保互不相同）

## terminology_and_expression_constraints
- required_terms:
  - 前序遍历 / 中序遍历 / 后序遍历
  - 根节点
  - 左子树 / 右子树
  - 叶子节点（或叶结点）
  - 树深度（或树的深度）
  - 唯一确定
- required_qualifiers:
  - 序列元素必须标注"互不相同"
  - 还原结果需说明表示方式（如"括号表示法"、"层序序列"、"文字描述结构"）
  - 涉及空子树时需明确说明"左子树为空"或"右子树为空"
- avoid_phrases:
  - "画出二叉树"（过于口语化，应改为"还原二叉树结构"）
  - "前序的第一个是根"（过于简化，应改为"前序序列的第一个元素为根节点"）
  - "中序的左边是左子树"（不严谨，应改为"中序序列中根节点左侧的元素构成左子树"）
- standard_rewrites:
  - bad: "根据前序和中序画出树" → good: "根据前序遍历序列和中序遍历序列还原二叉树的结构"
  - bad: "求树的深度" → good: "求该二叉树的深度"
  - bad: "有几个叶子" → good: "求该二叉树的叶子节点个数"

## audit_focus
- final_review_must_check:
  - 两种遍历序列是否对应同一棵二叉树（一致性）
  - 节点数 n 是否在 [6, 10] 范围内
  - 树深度 d 是否在 [3, 4] 范围内
  - 树结构是否满足：不是退化链、不是完全二叉树、至少一个节点有左右孩子
  - 叶子节点数是否 ≥ 2
  - 第2问是否明确依赖第1问的还原结果
  - 题干是否明确说明序列元素互不相同
  - 分值分配是否为 6+4=10
- solve_output_should_contain:
  - 还原的二叉树结构表示（括号表示法/层序序列/文字描述）
  - 还原过程的推理步骤（根节点定位、子树划分、递归还原）
  - 第2问性质的计算过程和最终结果
  - 两种遍历序列的一致性验证
- fail_if_missing:
  - 缺少二叉树还原结果
  - 两种遍历序列不一致（不对应同一棵树）
  - 树结构违反约束（退化链/完全二叉树/节点数越界/深度越界）
  - 第2问缺少基于还原树结构的计算过程
  - 题干未说明序列元素互不相同
