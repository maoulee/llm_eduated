## status

draft

## blueprint_contract

- slot_id: (未指定)
- question_type: single_choice
- score: (未指定)
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度
- examination_mode: 给定二叉树结构+叶子权值 → 计算WPL
- k_target: K1=2,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 3
- should_be:
  - 图形化二叉树+权值标注是最常见的呈现方式
  - 中等难度WPL题目通常涉及3-5个叶子结点，计算结果在20-80范围内
- should_not_be:
  - 路径长度从1开始计数（错误）
  - 只计算部分叶子结点
  - 将路径长度理解为结点层次
  - 权值与路径长度相乘时计算错误
- hard_constraints:
  - 叶子结点数量 (n): 3 ≤ n ≤ 5，整数
  - 权值 (w_i): 1 ≤ w_i ≤ 15，整数，各叶子权值可相同可不同
  - 树的高度 (h): 3 ≤ h ≤ 4，整数
  - 路径长度 (l_i): 由树结构决定，1 ≤ l_i ≤ h-1
  - WPL结果: 20 ≤ WPL ≤ 80
  - 一致性约束: 所有叶子结点路径长度之和应合理（避免全部在同一层）；权值与路径长度乘积之和应在目标范围内；树结构必须合法

## route

- question_form: single_choice
- question_type: computational
- requires_parameter_verification: true
- requires_solver: true
- requires_code: false

## core_knowledge_intent

- must_test:
  - 带权路径长度（WPL）的定义：WPL = Σ(w_i × l_i)，其中 w_i 为叶子权值，l_i 为该叶子到根结点的路径长度（边数）
  - 从二叉树图形中正确识别所有叶子结点及其权值
  - 正确计算每个叶子结点到根结点的路径长度（以边数计，根结点路径长度为0）
- must_not_shift_to:
  - 哈夫曼树的构造过程或最优二叉树判定
  - 二叉树的遍历算法（前序/中序/后序/层序）
  - 结点层次编号与路径长度的混淆（层次从1开始 vs 路径长度从0开始）
- coverage_success_criteria:
  - solver 能正确列出所有叶子结点、对应权值、对应路径长度，并计算加权和
  - 干扰项能覆盖路径长度计数起点错误、遗漏叶子结点、层次与路径长度混淆三类典型错误

## expected_reasoning_actions

- 观察二叉树图形，识别所有叶子结点（无左右子树的结点）
- 读取每个叶子结点标注的权值
- 从每个叶子结点出发，沿父指针向上追溯到根结点，统计经过的边数作为路径长度
- 对每个叶子结点，计算 权值 × 路径长度
- 将所有叶子的乘积求和，得到 WPL
- 将计算结果与四个选项比对，选出匹配项

## question_structure_plan

- stem_style: 图形化二叉树 + 文字设问。题干给出二叉树图形，每个叶子结点旁标注权值，设问要求计算该二叉树的带权路径长度。
- option_architecture:
  - correct: 正确 WPL 值（所有叶子 w_i × l_i 之和）
  - distractor_1（路径长度计数起点错误）：将路径长度从1开始计数（即 l_i' = l_i + 1），导致 WPL 偏大，偏差量 = Σw_i
  - distractor_2（遗漏叶子结点）：遗漏某个叶子结点（通常是最深层或权值较小的叶子），导致 WPL 偏小，偏差量 = 被遗漏叶子的 w_i × l_i
  - distractor_3（层次与路径长度混淆）：将结点的层次编号（根为第1层）当作路径长度，等价于路径长度从1开始计数，与 distractor_1 数值相同或相近，体现同一认知错误的不同表述路径
- asking_method: 直接设问"该二叉树的带权路径长度（WPL）为多少？"

## parameter_plan

- parameter_slots:
  - leaf_count: 叶子结点数量，候选范围 [3, 5]，用于决定树的结构复杂度
  - weights: 各叶子权值列表，候选范围 [1, 15] 整数，用于计算 WPL
  - tree_height: 树的高度，候选范围 [3, 4]，决定路径长度的上限
  - tree_structure: 二叉树拓扑结构，由 leaf_count 和 tree_height 共同决定，需保证合法且叶子分布在不同层
  - wpl_result: WPL 计算结果，目标范围 [20, 80]
- validation_targets:
  - WPL = Σ(w_i × l_i) 必须在 [20, 80] 范围内
  - 所有叶子结点的路径长度 l_i 必须 ≥ 1（根结点不能是叶子）
  - 叶子结点不能全部位于同一层（避免路径长度全部相同，降低区分度）
  - 四个选项必须互不相同
  - 干扰项数值必须与正确答案有合理差距（不能过于接近导致纯猜测）
- adjustment_priority:
  - 第一优先：调整权值使 WPL 落入 [20, 80]
  - 第二优先：调整树结构使叶子分布在至少两层
  - 第三优先：微调权值使干扰项与正确答案差距合理

## terminology_and_expression_constraints

- required_terms:
  - 带权路径长度 / WPL
  - 叶子结点 / 叶结点
  - 路径长度（明确为"从根结点到该结点的路径上的分支数"或"边数"）
  - 权值
- required_qualifiers:
  - 路径长度必须限定为"以边数计"或"分支数"，不能仅写"路径长度"而无说明
  - 若题干中出现"层次"一词，必须与"路径长度"明确区分
- avoid_phrases:
  - "路径长度从根结点开始为1"（错误表述，根结点路径长度为0）
  - "第n层结点的路径长度为n"（混淆层次与路径长度）
  - "结点的深度即为路径长度"（未说明深度从0还是1开始）
- standard_rewrites:
  - bad: "求该二叉树的路径长度" → good: "求该二叉树的带权路径长度（WPL）"
  - bad: "路径长度为从根到该结点的层数" → good: "路径长度为从根结点到该结点的路径上的分支数（边数）"
  - bad: "第3层结点的路径长度为3" → good: "第3层结点的路径长度为2（根结点为第1层，路径长度为边数）"

## audit_focus

- final_review_must_check:
  - 二叉树图形中所有叶子结点是否清晰可辨，权值标注是否无歧义
  - 路径长度的定义是否在题干或选项中明确为"边数"而非"层数"
  - WPL 计算结果是否在 [20, 80] 范围内
  - 四个选项是否互不相同
  - 干扰项是否对应 blueprint 中指定的三类错误（路径长度计数起点错误、遗漏叶子结点、层次与路径长度混淆）
  - 树结构是否合法（无悬空指针、无循环、叶子分布合理）
- solve_output_should_contain:
  - 所有叶子结点列表及其权值
  - 每个叶子结点的路径长度（边数）
  - 每个叶子的 w_i × l_i 乘积
  - WPL 求和过程及最终结果
  - 与正确选项的匹配确认
- fail_if_missing:
  - 缺少任一叶子结点的路径长度计算
  - WPL 结果不在 [20, 80] 范围内
  - 四个选项中有重复值
  - 干扰项无法对应到指定的错误认知路径
  - 树结构不合法（如叶子结点有子结点、根结点为叶子等）
