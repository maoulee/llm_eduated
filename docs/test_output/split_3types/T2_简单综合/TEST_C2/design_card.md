# Design Card — 二叉树遍历序列还原 + 后续分析

## status

draft

## blueprint_contract

- slot_id: DS-5-遍历序列还原-综合题
- question_type: comprehensive
- score: 10
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树 > 二叉树遍历
- primary_target_name: 二叉树遍历序列还原
- examination_mode: 遍历序列还原 + 后续分析模式
- k_target: K1=2, K2=3, K3=2, K4=3, K5=1
- difficulty_level: 3
- should_be:
  - 先序序列 + 中序序列能唯一确定一棵二叉树
  - q1 为核心题（4 分），q2/q3/q4 各自独立依赖 q1（star 依赖）
  - 树形态为非完全二叉树，左右子树不对称
  - 线索化指定节点为非根非叶节点，其中序前驱或后继至少一个不是直接父子关系
  - 度为 1 的节点数 ≥ 1，叶子节点数 ≥ 3
- should_not_be:
  - 不退化为链表（每个内部节点只有一个孩子）
  - 不使用完全二叉树或满二叉树
  - 不涉及平衡二叉树的旋转判定
  - 不涉及哈夫曼树构造
  - 不涉及二叉排序树的插入/删除
- hard_constraints:
  - 节点数 N: 7 ≤ N ≤ 11
  - 树高 H: 3 ≤ H ≤ 4
  - 节点标识: 大写字母 A～K，无重复
  - 先序与中序序列元素集合相同
  - sub_question_count: 4
  - sub_question_distribution: q1=4分, q2=2分, q3=2分, q4=2分

## route

- question_form: comprehensive
- question_type: mixed
- requires_parameter_verification: true
- requires_solver: true
- requires_code: true

## core_knowledge_intent

- must_test:
  - 先序 + 中序遍历序列唯一还原二叉树（递归分治执行能力）
  - 后序遍历序列的递归生成（左右根顺序的准确执行）
  - 中序线索化后指定节点的前驱/后继判断（线索指针与孩子指针的区分）
- must_not_shift_to:
  - 二叉排序树的插入/删除/查找操作
  - 平衡二叉树旋转判定
  - 哈夫曼树/并查集等扩展结构
- coverage_success_criteria:
  - 考生能从先序 + 中序序列正确重建二叉树结构（画出树形或给出层次描述）
  - 考生能基于重建结果准确推导后序序列、树高、叶子数及线索化前驱/后继

## expected_reasoning_actions

1. 从先序序列首元素定位二叉树的根节点
2. 在中序序列中找到根节点位置，划分左子树中序序列和右子树中序序列
3. 根据左子树长度从先序序列中截取左子树先序片段，右子树同理
4. 对左子树和右子树递归执行上述定位-划分-截取过程，直到子树为空
5. 对重建后的二叉树执行后序遍历（左右根），得到后序序列
6. 从重建的二叉树结构中统计叶子节点数和计算树高
7. 对指定非根非叶节点执行中序线索化，判断其前驱是左孩子还是左子树最右下节点，后继是右孩子还是右子树最左下节点

## question_structure_plan

- question_form: comprehensive
- shared_context: 给定一棵二叉树的先序遍历序列和中序遍历序列（大写字母标识，无重复），据此回答以下问题
- sub_question_chain:
  - q1（4分）: 根据先序 + 中序遍历序列画出（或描述）该二叉树的结构。依赖条件：先序序列 + 中序序列。核心题，后续所有子问题依赖 q1 的结果。
  - q2（2分）: 写出该二叉树的后序遍历序列。依赖：q1 的树结构。
  - q3（2分）: 求该二叉树的树高和叶子节点数。依赖：q1 的树结构。
  - q4（2分）: 对该二叉树进行中序线索化后，判断题目指定节点（非根非叶）的中序前驱和中序后继分别是哪个节点，并说明是通过孩子指针到达还是通过线索指针到达。依赖：q1 的树结构。
- dependency_pattern: star（q1 为中心，q2/q3/q4 均依赖 q1，彼此独立）
- 选定干扰策略:
  - q2 干扰 — 顺序倒置：后序遍历中"左右根"被误写为"右左根"或"左根右"（中序混入）
  - q3 干扰 — 偏移错误：树高计算时根节点高度从 0 起算（off-by-one），导致树高少 1
  - q4 干扰 — 概念混淆：将中序前驱/后继与父节点/兄弟节点混淆，忽略度为 1 节点的线索指针方向判断

## parameter_plan

- parameter_slots:
  - name: preorder_sequence
    role: 二叉树的先序遍历序列，作为还原的唯一输入之一
    candidate_range: 大写字母 A～K 的排列，长度 7～11
    used_by: q1, q2, q3, q4
  - name: inorder_sequence
    role: 二叉树的中序遍历序列，与先序序列配合还原树结构
    candidate_range: 与 preorder_sequence 元素集合相同，排列不同，长度 7～11
    used_by: q1, q2, q3, q4
  - name: node_count
    role: 节点总数，约束序列长度
    candidate_range: 7 ≤ N ≤ 11
    used_by: q1
  - name: tree_height
    role: 树高，由树形态决定，约束树的深度
    candidate_range: 3 ≤ H ≤ 4
    used_by: q3
  - name: threading_target_node
    role: q4 中指定的线索化分析目标节点
    candidate_range: 非根非叶节点，且其中序前驱或后继至少一个不是直接父子关系
    used_by: q4
- validation_targets:
  - 先序序列和中序序列的元素集合完全相同（同一组字母，无遗漏无重复）
  - 先序 + 中序序列能唯一确定一棵二叉树（递归划分过程中无歧义）
  - 重建后的树高在 3～4 范围内
  - 重建后的叶子节点数 ≥ 3
  - 重建后的树中度为 1 的节点数 ≥ 1
  - 树形态为非完全二叉树，左右子树不对称
  - threading_target_node 确实是非根非叶节点，且其中序前驱或后继至少一个需要通过线索指针（而非孩子指针）到达
- adjustment_priority:
  - 1st: 调整 preorder_sequence / inorder_sequence 的具体排列以控制树形态（非完全、不对称、高度 3～4）
  - 2nd: 确保度为 1 的节点数 ≥ 1 且叶子数 ≥ 3
  - 3rd: 选定 threading_target_node 使其线索化分析有区分度

## terminology_and_expression_constraints

- required_terms:
  - 先序遍历序列
  - 中序遍历序列
  - 后序遍历序列
  - 中序线索化
  - 中序前驱
  - 中序后继
  - 树高
  - 叶子节点
- required_qualifiers:
  - 提到"线索化"时必须限定为"中序线索化"，不可只写"线索化"
  - q4 中提到前驱/后继时必须限定为"中序前驱"/"中序后继"
  - 提到树高时需明确"从根节点到最远叶子节点的路径上的节点数"（或边数，需在题干中统一定义）
- avoid_phrases:
  - "二叉搜索树" / "二叉排序树" — 本题不涉及
  - "平衡因子" / "AVL" — 本题不涉及
  - "层序遍历" — 本题不涉及
  - 仅写"前驱"/"后继"而不加"中序"限定
- standard_rewrites:
  - bad: "线索化后该节点的前驱"
    good: "中序线索化后该节点的中序前驱"
  - bad: "画出二叉树"
    good: "根据给定的先序遍历序列和中序遍历序列，画出该二叉树的结构（标明各节点的左右孩子关系）"
  - bad: "求树的高度"
    good: "求该二叉树的树高（根节点所在的层为第 1 层）"

## audit_focus

- final_review_must_check:
  - 先序序列与中序序列元素集合完全一致，无遗漏无重复
  - 先序 + 中序序列确实能唯一确定一棵二叉树（不存在多种合法重建）
  - 重建后的树形态满足全部参数约束：7 ≤ N ≤ 11、3 ≤ H ≤ 4、叶子 ≥ 3、度为 1 节点 ≥ 1、非完全二叉树、左右子树不对称
  - threading_target_node 满足"非根非叶"且"中序前驱或后继至少一个不是直接父子关系"
  - 题干中树高的定义方式（按层还是按边）已明确且一致
  - 所有术语均使用限定语（"中序线索化""中序前驱""中序后继"）
  - 子问题分值合计 = 10 分（q1=4 + q2=2 + q3=2 + q4=2）
  - 干扰策略已在 question_structure_plan 中选定 3 种，分别对应 q2/q3/q4 的常见错误
- solve_output_should_contain:
  - 重建二叉树的结构表示（树形图或层次描述），作为 q2/q3/q4 的推导依据
  - 后序遍历序列（q2 的答案）
  - 树高和叶子节点数的计算结果（q3 的答案）
  - threading_target_node 的中序前驱和后继节点标识，以及判断依据（孩子指针 vs 线索指针）（q4 的答案）
  - 参数验证通过的证据（先序中序一致性、树形态约束满足、threading_target_node 约束满足）
- fail_if_missing:
  - 先序与中序序列元素集合不一致
  - 先序 + 中序无法唯一确定二叉树
  - 树形态退化为链表或为完全/满二叉树
  - threading_target_node 是根节点或叶子节点
  - threading_target_node 的中序前驱和后继都是直接父子关系（无区分度）
  - 子问题依赖关系不是 star 结构
  - 题干中缺少树高定义
