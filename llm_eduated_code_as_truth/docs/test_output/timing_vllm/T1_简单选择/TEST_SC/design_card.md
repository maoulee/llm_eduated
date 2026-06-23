## status
draft

## blueprint_contract
- slot_id: (未指定)
- question_type: single_choice
- score: (未指定)
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度
- examination_mode: 给定二叉树结构+叶子节点权值，计算WPL
- k_target: K1=2,K2=3,K3=3,K4=2,K5=2
- difficulty_level: 3
- should_be:
  - 仅叶子节点有权值
  - 路径长度从根节点开始为0
  - WPL = Σ(w_i × path_length_i)
- should_not_be:
  - 非叶子节点参与WPL计算
  - 路径长度从1开始计数
  - 权值分配错误
  - 算术错误
- hard_constraints:
  - 节点总数 N: [5, 10]，建议6-8个
  - 叶子节点数 L: [3, 5]，约束 L ≤ N/2 + 1
  - 树的高度 H: [3, 4]，约束 H ≥ ⌈log₂(N+1)⌉
  - 叶子节点权值 w_i: [1, 20]，各权值应不同
  - WPL结果范围: [20, 100]

## route
- question_form: single_choice
- question_type: computational
- requires_parameter_verification: true
- requires_solver: true
- requires_code: true

## core_knowledge_intent
- must_test:
  - WPL定义：带权路径长度为所有叶子节点的权值与其到根节点路径长度乘积之和
  - 路径长度计数规则：根节点路径长度为0，逐层递增
  - 仅叶子节点参与WPL计算，非叶子节点权值不计入
- must_not_shift_to:
  - 哈夫曼树构造过程（本题不要求构造最优二叉树）
  - 非叶子节点权值参与计算
- coverage_success_criteria:
  - 学生能正确识别所有叶子节点并读取其权值
  - 学生能正确计算每个叶子节点到根的路径长度（从0开始）
  - 学生能正确执行加权求和得到WPL

## design_rationale
本题以"给定二叉树结构+叶子节点权值，计算WPL"为考察模式，旨在检验学生对二叉树带权路径长度这一核心概念的完整理解与计算能力。选择此考点组合的原因在于：WPL是树结构中最具代表性的加权度量指标，既要求学生理解路径长度的定义（从根为0开始计数），又要求学生区分叶子节点与非叶子节点的角色差异，同时涉及中等规模的加权求和运算。K-雷达形状（K1=2,K2=3,K3=3,K4=2,K5=2）呈现"中间高两头低"的分布，反映本题以理解应用为主、记忆和创造为辅的定位——学生需要回忆WPL定义（K1=2），理解路径长度计数规则（K2=3），应用公式进行逐项计算（K3=3），但无需复杂分析或创新（K4=2,K5=2）。这种设计能区分两类学生：一类能完整执行"识别叶子→读取权值→计算路径长度→加权求和"全流程并自我校验的学生；另一类仅模糊记得WPL概念但在路径长度起点、节点筛选或算术细节上出错的学生。4个干扰项分别对应四种典型认知错误路径，确保错误不是随机猜测而是有迹可循的概念偏差。

## expected_reasoning_actions
- 观察二叉树图形结构，识别所有叶子节点（无子节点的节点）
- 从权值表中读取每个叶子节点对应的权值
- 对每个叶子节点，从根节点出发逐层追踪到该叶子，计算路径长度（根节点为第0层）
- 将每个叶子节点的权值与其路径长度相乘，得到该叶子的带权路径
- 将所有叶子节点的带权路径相加，得到WPL
- 检查计算过程：确认仅叶子节点参与计算、路径长度从0开始、算术无误

## question_structure_plan
- stem_style: 图形+表格混合呈现——给出二叉树结构图（标注节点标识），另附叶子节点权值表
- asking_method: 直接设问"该二叉树的带权路径长度（WPL）为多少？"
- option_architecture:
  - correct: 正确WPL值（仅叶子节点、路径从0开始、正确加权求和）
  - distractor_1: 包含非叶子节点权值的计算结果（错误认知：所有节点都参与WPL计算）
  - distractor_2: 路径长度从1开始计数的结果（错误认知：根节点路径长度为1）
  - distractor_3: 权值分配错误或算术错误的结果（错误认知：权值与节点对应关系混淆或计算失误）
- distractor_strategy_selected:
  - 非叶节点纳入（计算型干扰）
  - 偏移错误（路径长度起点off-by-one）
  - 权值分配错误/算术错误（计算型干扰）

## parameter_plan
- parameter_slots:
  - N（节点总数）: role=控制树规模, candidate_range=[5,10], used_by=树结构生成
  - L（叶子节点数）: role=控制WPL求和项数, candidate_range=[3,5], used_by=权值表生成
  - H（树高度）: role=控制路径长度范围, candidate_range=[3,4], used_by=树结构生成
  - w_i（各叶子权值）: role=WPL计算输入, candidate_range=[1,20]且互不相同, used_by=权值表
  - WPL_result（正确答案）: role=正确选项值, candidate_range=[20,100], used_by=选项生成
- validation_targets:
  - WPL_result 必须在 [20, 100] 范围内
  - 各叶子权值互不相同
  - L ≤ N/2 + 1
  - H ≥ ⌈log₂(N+1)⌉
  - 仅叶子节点有权值，非叶子节点无权值
  - 路径长度从根节点0开始计数
- adjustment_priority:
  - 第一优先：确保WPL_result在[20,100]范围内
  - 第二优先：确保各干扰项与正确答案数值不同且互不相同
  - 第三优先：调整权值分布使计算量适中

## terminology_and_expression_constraints
- required_terms:
  - 带权路径长度 / WPL
  - 叶子节点 / 叶结点
  - 路径长度
  - 根节点
- required_qualifiers:
  - 必须明确"路径长度从根节点开始为0"或等价表述
  - 必须明确"仅叶子节点有权值"或等价表述
- avoid_phrases:
  - "深度"（易与路径长度混淆，应使用"路径长度"）
  - "层数"（易产生从1开始计数的歧义）
  - "所有节点"（应明确限定为"叶子节点"）
- standard_rewrites:
  - bad: "计算各节点到根的距离" → good: "计算各叶子节点到根节点的路径长度"
  - bad: "从第1层开始" → good: "根节点的路径长度为0"
  - bad: "所有节点的权值乘以路径长度" → good: "所有叶子节点的权值乘以其路径长度"

## audit_focus
- final_review_must_check:
  - 题干中二叉树图形与权值表一致（节点标识对应正确）
  - 仅叶子节点在权值表中出现，非叶子节点无权值
  - 路径长度定义明确为从根节点0开始
  - 正确答案WPL在[20,100]范围内
  - 4个选项数值互不相同
  - 干扰项对应设计卡中选定的3种干扰策略
- solve_output_should_contain:
  - 每个叶子节点的标识、权值、路径长度
  - 每个叶子节点的带权路径（权值×路径长度）
  - WPL求和过程与最终结果
  - 干扰项生成依据（对应哪种错误认知路径）
- fail_if_missing:
  - 缺少叶子节点识别过程
  - 路径长度计算未体现从0开始
  - 非叶子节点参与了WPL计算
  - 正确答案不在[20,100]范围内
  - 干扰项与正确答案数值重复
