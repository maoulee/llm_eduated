## status

draft

## blueprint_contract

- slot_id: DS-5-树与二叉树-二叉树带权路径长度
- question_type: single_choice
- score: 未指定
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度
- examination_mode: 给定二叉树结构计算WPL
- k_target: K1=2,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 3
- should_be:
  - 给定二叉树结构（图形或数组表示），标注叶子结点权值，计算WPL
  - 叶子结点数量 3-6 个，建议 4-5 个
  - 权值范围 1-20，整数，各权值可不同
  - 树高度 3-4 层
  - WPL 计算结果在 50-200 范围内
- should_not_be:
  - 路径长度从 1 开始计数
  - 漏算叶子结点
  - 混淆层数与路径长度
  - 乘法计算错误
- hard_constraints:
  - leaf_count: 3 ≤ leaf_count ≤ 6
  - weight_i: 1 ≤ weight_i ≤ 20
  - path_length_i: 0 ≤ path_length_i ≤ 3
  - height: 3 ≤ height ≤ 4
  - WPL_result: 50 ≤ WPL ≤ 200
  - 树结构合法，所有叶子结点路径长度之和合理

## route

- question_form: single_choice
- question_type: computational
- requires_parameter_verification: true
- requires_solver: true
- requires_code: false

## core_knowledge_intent

- must_test:
  - 带权路径长度（WPL）的定义：WPL = Σ(叶子结点权值 × 该叶子结点的路径长度)
  - 路径长度的计算：从根结点到该结点所经过的边数（根结点路径长度为 0）
  - 叶子结点的识别：无左右子树的结点
- must_not_shift_to:
  - 哈夫曼树的构造过程
  - 一般树（非二叉树）的 WPL 计算
  - 结点深度与路径长度的概念混淆
- coverage_success_criteria:
  - 学生能正确识别所有叶子结点并读取其权值
  - 学生能正确计算每个叶子结点的路径长度（边数）
  - 学生能正确执行加权求和得到 WPL

## design_rationale

本题以"给定二叉树结构计算WPL"为考察模式，选择中等难度（K=3），K-雷达形状为 K2/K3 突出（理解与应用为主）、K1/K4 中等、K5 较低。设计意图是考查学生对 WPL 核心概念的扎实掌握——不是记忆公式，而是能在具体树结构上完整执行"识别叶子→确定路径长度→加权求和"的计算流程。这种设问方式能区分两类学生：一类能完整走完计算流程并自我检查（正确识别所有叶子、路径长度从根起算边数、逐项加权后求和），另一类只记得 WPL 名称或公式但执行时出现路径长度计数起点错误、漏算叶子、层数与路径长度混淆等典型认知偏差。4-5 个叶子结点、3-4 层树高的参数规模适中，既保证计算量足以暴露错误路径，又不至于因规模过大而变成纯算术题，符合考研数据结构选择题的考查定位。

## expected_reasoning_actions

- 观察二叉树结构图，识别所有叶子结点（无左右子树的结点）
- 读取每个叶子结点标注的权值
- 从根结点出发，逐条边计数，确定每个叶子结点的路径长度（根到该结点的边数）
- 对每个叶子结点执行 权值 × 路径长度 的乘法运算
- 将所有叶子结点的加权乘积求和，得到 WPL
- 将计算结果与四个选项比对，选出匹配项

## question_structure_plan

- stem_style: 图形化二叉树 + 文字设问。题干给出二叉树结构图（结点标注权值），设问"该二叉树的带权路径长度 WPL 为多少？"
- option_architecture:
  - correct: 正确 WPL 计算结果
  - distractor_1（路径长度计数起点错误）：路径长度从 1 开始计数（而非从 0），导致每个叶子结点路径长度 +1，WPL 偏大
  - distractor_2（漏算叶子结点）：遗漏某个叶子结点未参与加权求和，WPL 偏小
  - distractor_3（层数与路径长度混淆）：将结点的层数（根为第 1 层）当作路径长度，导致路径长度整体 +1，WPL 偏大
- asking_method: 直接计算型设问，要求给出 WPL 的具体数值

## parameter_plan

- parameter_slots:
  - tree_structure: 二叉树的拓扑结构（父子关系），决定各结点路径长度；候选范围：高度 3-4 层，4-5 个叶子结点
  - leaf_weights: 各叶子结点的权值；候选范围：1-20 的整数，各权值可不同
  - internal_node_labels: 非叶子结点的标识（可选权值或仅字母标识）
- validation_targets:
  - WPL 计算结果必须在 50-200 范围内
  - 所有叶子结点路径长度 ≤ 3
  - 树结构合法（每个结点最多两个子结点）
  - 四个选项互不相同且均为整数
  - 干扰项与正确项数值差距合理（非极端接近或极端远离）
- adjustment_priority:
  - 优先调整 leaf_weights 使 WPL 落入 50-200 范围
  - 其次调整 tree_structure 控制路径长度分布
  - 最后微调确保干扰项数值合理

## terminology_and_expression_constraints

- required_terms:
  - 带权路径长度 / WPL
  - 叶子结点 / 叶结点
  - 路径长度
  - 根结点
- required_qualifiers:
  - 路径长度必须明确为"从根结点到该结点所经过的边数"
  - 若题干中出现"层"的概念，需与"路径长度"明确区分
- avoid_phrases:
  - "深度"（易与路径长度混淆，应使用"路径长度"）
  - "层数"代替"路径长度"（层数从 1 起，路径长度从 0 起）
  - "所有结点的权值"（WPL 只涉及叶子结点权值）
- standard_rewrites:
  - bad: "该结点的深度为 2" → good: "从根结点到该结点的路径长度为 2"
  - bad: "第 3 层的结点" → good: "路径长度为 2 的结点"（若需表达层位置）
  - bad: "所有结点的权值" → good: "叶子结点的权值"

## audit_focus

- final_review_must_check:
  - 二叉树结构图清晰，父子关系无歧义
  - 所有叶子结点权值标注明确，无遗漏
  - 路径长度定义与题干表述一致（从根起算边数）
  - WPL 计算结果在 50-200 范围内
  - 四个选项互不相同
  - 三个干扰项分别对应三种典型错误认知路径（计数起点错误、漏算叶子、层数混淆）
- solve_output_should_contain:
  - 每个叶子结点的权值和路径长度
  - 每个叶子结点的加权乘积（权值 × 路径长度）
  - WPL 求和过程与最终结果
  - 干扰项生成逻辑说明
- fail_if_missing:
  - 缺少叶子结点识别过程
  - 路径长度计算未体现"从根起算边数"
  - WPL 结果不在 50-200 范围内
  - 干扰项无法对应到明确的错误认知路径
