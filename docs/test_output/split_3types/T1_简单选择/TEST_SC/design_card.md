# Design Card

## status

draft

## blueprint_contract

- slot_id: 待分配
- question_type: single_choice
- score: 2
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度(WPL)
- examination_mode: 给定二叉树结构+叶子权值→计算WPL
- k_target: K1=2, K2=2, K3=2, K4=1, K5=2
- difficulty_level: 3
- should_be:
  - 考生必须按路径长度（根到叶子节点的边数）逐叶计算 WPL
  - 路径长度定义（边数，根为0）是核心区分点
  - 计算量适中（4-6 个叶子求和），允许非完全二叉树
  - 干扰项设计须体现典型认知错误，非随机数值
- should_not_be:
  - 不考 Huffman 树的构造过程
  - 不考 WPL 的性质推导或最小性证明
  - 不涉及哈夫曼编码
  - 不出现深度超过4层的树（避免计算量过大）
- hard_constraints:
  - 树深度 3-4 层（根为第1层）
  - 叶子节点数 4-6 个
  - 叶子权值正整数 1-9，不可为0
  - 叶子路径长度（到根边数）2-3
  - WPL 正确答案值范围约 30-80
  - 每个干扰项与正确答案绝对差 ≥ 3
  - 选项数 4

## route

- question_form: single_choice
- question_type: computational
- requires_parameter_verification: true
- requires_solver: true
- requires_code: true

## core_knowledge_intent

- must_test:
  - 路径长度的精确定义：从根到某节点的路径上的边数（根节点路径长度为0）
  - WPL = Σ（叶子权值 × 对应路径长度），逐叶求和
  - 在非完全二叉树中正确识别全部叶子节点
- must_not_shift_to:
  - 不偏移到 Huffman 树构造或最优性证明
  - 不偏移到二叉树的遍历或其它树属性（如高度、节点总数）计算
- coverage_success_criteria:
  - 考生能区分"层数（从1计）"与"路径长度（边数，从0计）"的差异
  - 考生能从树结构图中完整识别所有叶子节点并逐一计算加权路径

## expected_reasoning_actions

1. 从给定的二叉树结构图中识别所有叶子节点（度为0的节点）
2. 对每个叶子节点，确定其到根的路径长度（路径上的边数，根节点为0）
3. 对每个叶子节点，将其权值乘以对应的路径长度，得到该叶子的带权路径长度
4. 将所有叶子的带权路径长度求和，得到整棵树的 WPL
5. 将计算结果与四个选项对比，选出正确答案
6. （排误）检查是否存在用层数代替边数、误纳内部节点、漏算叶子等常见错误对应的干扰项

## question_structure_plan

- stem_style: 图示题——给出二叉树结构图（标注各叶子权值），要求计算该树的 WPL
- asking_method: "该二叉树的带权路径长度（WPL）为"
- option_architecture:
  - correct: 按路径长度（边数，根为0）逐叶计算的正确 WPL
  - distractor_1（偏移错误）: 路径长度按层数（从1计）而非边数（从0计），每个叶子路径长度系统性+1，结果偏高
  - distractor_2（非叶节点纳入）: 误将某内部节点也计入加权路径求和，结果偏高
  - distractor_3（中间值/漏算）: 漏算一个叶子的贡献或叶子识别错误（将某叶子误认为非叶子），结果偏低
- distractor_strategy_note: 每个干扰项对应一个确定性错误算法，由 solve.py 实现并生成数值，不硬编码干扰值
- condition_count: 2-3（树结构描述 + 权值标注 + 可能的非完全性说明）

## parameter_plan

- parameter_slots:
  - tree_structure:
    - role: 定义二叉树的形态（节点连接关系），决定叶子集合和每个叶子的深度
    - candidate_range: 深度3-4层，叶子4-6个，允许非完全二叉树
    - used_by: 正确算法 + 全部干扰算法
  - leaf_weights:
    - role: 每个叶子节点的权值（正整数）
    - candidate_range: 1-9，不可为0，不可重复以确保计算无歧义
    - used_by: 正确算法 + 全部干扰算法
  - path_length_definition:
    - role: 路径长度的取值方式（边数 vs 层数），区分正确与干扰1
    - candidate_range: 固定——正确用边数（根为0），干扰1用层数（根为1）
    - used_by: 正确算法 / distractor_1
  - leaf_set_definition:
    - role: 叶子节点集合的识别，区分正确与干扰2/3
    - candidate_range: 正确取度为0的节点；干扰2纳入一个内部节点；干扰3排除一个真实叶子
    - used_by: 正确算法 / distractor_2 / distractor_3
- validation_targets:
  - 正确 WPL 值落在 30-80 范围内
  - distractor_1（层数法）与正确值绝对差 ≥ 3
  - distractor_2（含内部节点）与正确值绝对差 ≥ 3
  - distractor_3（漏算叶子）与正确值绝对差 ≥ 3
  - 四个选项互不相同
  - 所有叶子路径长度（边数）在 2-3 范围内
  - 树深度 3-4 层（根为第1层）
- adjustment_priority:
  1. 首先确定树结构和权值，使正确 WPL 落在 30-80
  2. 验证三个干扰项偏差均 ≥ 3，若不满足则调整权值或树结构
  3. 确保叶子路径长度均为 2-3，无过浅或过深叶子

## terminology_and_expression_constraints

- required_terms:
  - "带权路径长度（WPL）"
  - "路径长度"（须在题干或注释中明确为"从根到该节点的边数"）
  - "叶子节点"（度为0的节点）
  - "权值"
- required_qualifiers:
  - 计算对象限定为"所有叶子节点"，不含内部节点
  - 若树为非完全二叉树，需在图中清晰标注结构，避免节点对应歧义
- avoid_phrases:
  - 避免使用"路径的长度"而不定义——易与"层数"混淆
  - 避免直接给"路径长度 = 层数 - 1"的公式提示——降低区分度
  - 避免使用 Huffman 树相关术语——防止考点偏移
- standard_rewrites:
  - bad: "该树的 WPL 是多少"
  - good: "该二叉树的带权路径长度（WPL）为多少？注：路径长度为从根节点到该节点的边数。"
  - bad: "叶子到根的距离"
  - good: "从根节点到该叶子节点的路径长度（边数）"

## audit_focus

- final_review_must_check:
  - 题干是否明确给出路径长度的定义（边数，根为0），或通过标准术语隐含表达
  - 二叉树结构图是否清晰无歧义，所有叶子节点可被唯一识别
  - 权值标注是否与叶子节点一一对应
  - 四个选项是否互不相同且每个干扰项与正确值绝对差 ≥ 3
  - 正确 WPL 是否落在 30-80 范围
  - 是否未涉及 Huffman 树构造、编码、最优性等内容
  - 干扰项是否对应明确的错误算法（非随机数值）
- solve_output_should_contain:
  - 正确 WPL 数值
  - 三个干扰项数值及其对应的错误算法说明（层数法、含内部节点、漏算叶子）
  - 每个叶子的权值、路径长度（边数）、单项贡献的列表
  - 四个选项值及正确选项标号
  - 验证断言：所有偏差 ≥ 3，WPL 在 30-80 范围内，四值互异
- fail_if_missing:
  - 路径长度定义缺失（考生无法判断用边数还是层数）
  - 树结构图无法唯一确定叶子集合
  - 任一干扰项与正确值绝对差 < 3
  - 正确 WPL 超出 30-80 范围
  - 出现 Huffman 相关内容
  - 叶子权值含0或超出1-9范围
