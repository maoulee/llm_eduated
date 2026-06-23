## status
draft

## blueprint_contract
- slot_id: (未指定)
- question_type: single_choice
- score: (未指定)
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度
- examination_mode: 给定二叉树结构计算WPL
- k_target: K1=2,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 3
- should_be:
  - 节点总数N在[5,10]范围内，建议6-8个
  - 叶子节点数L在[3,5]范围内
  - 树高H在[3,4]范围内
  - 叶子节点权值W_i为[1,50]范围内的整数
  - WPL计算结果在[50,500]范围内
  - 至少一个叶子节点路径长度≥2
  - 权值分配应有差异
  - 树结构清晰无歧义
- should_not_be:
  - 不应考查哈夫曼树的构造过程
  - 不应考查二叉树遍历算法的代码实现
  - 不应涉及多知识点综合
- hard_constraints:
  - 节点总数N: [5, 10]
  - 叶子节点数L: [3, 5]，需满足 L ≤ N
  - 树的高度H: [3, 4]，与N需结构一致
  - 叶子节点权值W_i: [1, 50]，整数
  - WPL结果范围: [50, 500]
  - 至少一个叶子节点路径长度≥2
  - 权值分配应有差异
  - 树结构清晰无歧义

## route
- question_form: single_choice
- question_type: computational
- requires_parameter_verification: true
- requires_solver: true
- requires_code: false

## core_knowledge_intent
- must_test:
  1. WPL的定义：二叉树中所有叶子节点的权值乘以其路径长度之和
  2. 路径长度的正确计算：从根节点到该叶子节点所经过的边数（分支数）
  3. WPL计算规则：仅计入叶子节点，非叶子节点不参与计算
- must_not_shift_to:
  1. 不应偏移到哈夫曼树的构造与最优性证明
  2.I have to give the solution based on the reasoning directly now.</think>

## status
draft

## blueprint_contract
- slot_id: (未指定)
- question_type: single_choice
- score: (未指定)
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度
- examination_mode: 给定二叉树结构计算WPL
- k_target: K1=2,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 3
- should_be:
  - 节点总数N在[5,10]范围内，建议6-8个
  - 叶子节点数L在[3,5]范围内
  - 树高H在[3,4]范围内
  - 叶子节点权值W_i为[1,50]范围内的整数
  - WPL计算结果在[50,500]范围内
  - 至少一个叶子节点路径长度≥2
  - 权值分配应有差异
  - 树结构清晰无歧义
- should_not_be:
  - 不应考查哈夫曼树的构造过程
  - 不应考查二叉树遍历算法的代码实现
  - 不应涉及多知识点综合
- hard_constraints:
  - 节点总数N: [5, 10]
  - 叶子节点数L: [3, 5]，需满足 L ≤ N
  - 树的高度H: [3, 4]，与N需结构一致
  - 叶子节点权值W_i: [1, 50]，整数
  - WPL结果范围: [50, 500]
  - 至少一个叶子节点路径长度≥2
  - 权值分配应有差异
  - 树结构清晰无歧义

## route
- question_form: single_choice
- question_type: computational
- requires_parameter_verification: true
- requires_solver: true
- requires_code: false

## core_knowledge_intent
- must_test:
  1. WPL的定义：二叉树中所有叶子节点的权值乘以其路径长度之和
  2. 路径长度的正确计算：从根节点到该叶子节点所经过的边数（分支数）
  3. WPL计算规则：仅计入叶子节点，非叶子节点不参与计算
- must_not_shift_to:
  1. 不应偏移到哈夫曼树的构造与最优性证明
  2. 不应偏移到二叉树遍历算法的实现细节
- coverage_success_criteria:
  1. 能正确识别树中所有叶子节点（无遗漏无多余）
  2. 能正确计算每个叶子节点的路径长度并应用WPL公式求和

## design_rationale
本题采用"给定二叉树图形+权值标注→计算WPL"的经典设问方式，考察意图是检验学生对WPL核心概念的掌握程度：能否准确识别叶子节点、能否正确计算路径长度、能否理解"仅叶子节点参与计算"这一关键规则。选择6-8个节点、3-4个叶子、树高3-4层的中等规模结构，是因为这个规模既能体现多层路径长度的差异（避免所有叶子在同一层导致题目退化），又不会因节点过多增加不必要的计算负担。K-雷达形状（K2=3,K3=3为核心）反映本题重在理解应用而非记忆或创新：K2考查对WPL定义的理解，K3考查在给定结构上正确执行计算流程的能力。这种设计能区分两类学生：一类能完整走完"识别叶子→计算路径→加权求和"流程并自我检查的学生，另一类只模糊记得WPL概念但在路径长度计数或叶子识别上出现典型错误的学生。中等难度（difficulty=3）适合考查这一基础但易错的核心概念。

## expected_reasoning_actions
- 观察二叉树图形，识别出所有叶子节点（无左右子节点的节点）
- 对每个叶子节点，从根节点出发沿唯一路径到达该节点，统计经过的边数作为路径长度
- 将每个叶子节点的权值与其路径长度相乘，得到该节点的带权路径
- 将所有叶子节点的带权路径求和，得到整棵树的WPL
- 验证计算过程：确认未计入非叶子节点、路径长度计数正确、权值与节点对应无误

## question_structure_plan
- stem_style: 图形化二叉树表示，节点内标注权值，树结构清晰无歧义
- option_architecture:
  - 1个正确选项：正确WPL计算结果
  - 3个干扰选项，分别对应以下错误认知路径：
    1. 干扰类型A（概念混淆）：将非叶子节点的权值也计入WPL求和
    2. 干扰类型B（偏移错误）：路径长度计算错误，如从1开始计数而非从0开始，或层数与路径长度混淆
    3. 干扰类型C（张冠李戴）：权值与路径长度对应错误，将某个叶子节点的权值错误地匹配到另一个叶子节点的路径长度上
- asking_method: 直接计算型设问，题干给出二叉树图形及权值，问"该二叉树的带权路径长度WPL为"

## parameter_plan
- parameter_slots:
  - 节点总数N: 角色=树规模控制，候选范围=[5,10]，建议值=6-8，used_by=树结构生成
  - 叶子节点数L: 角色=WPL计算复杂度控制，候选范围=[3,5]，约束=L≤N，used_by=树结构生成
  - 树高H: 角色=路径长度差异控制，候选范围=[3,4]，约束=与N结构一致，used_by=树结构生成
  - 叶子节点权值W_i: 角色=WPL计算输入，候选范围=[1,50]整数，建议不完全相同，used_by=WPL计算
  - 非叶子节点权值: 角色=干扰项生成素材，候选范围=[1,50]整数，used_by=干扰项A生成
- validation_targets:
  - WPL计算结果应在[50,500]范围内
  - 至少一个叶子节点的路径长度≥2（确保有多层结构）
  - 各叶子节点权值应有差异（避免所有权值相同导致题目退化）
  - 树结构应清晰无歧义（每个节点的左右子关系明确）
- adjustment_priority:
  1. 先确定树的结构（N、L、H及父子关系）
  2. 再为叶子节点分配权值W_i
  3. 计算WPL并验证结果在[50,500]范围内
  4. 若WPL超出范围，调整权值分配而非改变树结构
  5. 最后为非叶子节点分配权值（用于干扰项生成）

## terminology_and_expression_constraints
- required_terms:
  - 带权路径长度（WPL）
  - 叶子节点（或叶结点）
  - 路径长度
- required_qualifiers:
  - 路径长度应明确定义为"从根节点到该节点所经过的边数"或"分支数"
  - 若使用"层"的概念，需明确根节点为第1层（或第0层），避免歧义
- avoid_phrases:
  - "节点深度"（需明确定义是从根开始计还是从1开始计）
  - "第k层"（易与路径长度混淆，k层节点的路径长度为k-1）
  - "权值之和"（未体现路径长度的加权，易误导）
- standard_rewrites:
  - bad: "第3层的叶子节点" → good: "路径长度为2的叶子节点"
  - bad: "节点深度为3" → good: "从根到该节点的路径长度为3"
  - bad: "所有节点权值乘以层数之和" → good: "所有叶子节点的权值乘以其路径长度之和"

## audit_focus
- final_review_must_check:
  1. 二叉树图形表示清晰，每个节点的左右子关系无歧义
  2. 所有叶子节点的权值标注完整且清晰可读
  3. WPL正确计算结果在[50,500]范围内
  4. 至少存在一个路径长度≥2的叶子节点
  5. 3个干扰项分别对应明确的错误认知路径（非叶子计入、路径长度错误、权值对应错误）
  6. 干扰项数值与正确结果有合理差异（非随机数）
- solve_output_should_contain:
  1. 识别出的所有叶子节点列表（标注节点标识或位置）
  2. 每个叶子节点的路径长度计算过程
  3. 每个叶子节点的（权值×路径长度）中间结果
  4. 最终WPL求和结果及计算式
  5. 明确说明非叶子节点不参与WPL计算
- fail_if_missing:
  1. 缺少叶子节点识别步骤或识别结果不完整
  2. 路径长度计算无依据（未展示从根到叶子的路径）
  3. 未说明"仅叶子节点参与WPL计算"这一关键规则
  4. 干扰项无法对应到明确的错误认知路径
  5. WPL计算结果不在[50,500]范围内
