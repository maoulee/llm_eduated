# Design Card — 二叉树带权路径长度(WPL)计算

## status

draft

## blueprint_contract

- slot_id: DS-5-WPL-CALC
- question_type: single_choice
- score: 2
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度(WPL)
- examination_mode: 计算型——WPL公式计算与树结构分析
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 3
- should_be:
  - 正向计算 WPL：给定二叉树结构和叶子权值，用 WPL = Σ(权值 × 路径长度) 求和
  - 路径长度定义为从根到该节点的边数（根节点路径长度为 0，其子节点为 1，依此类推）
  - 至少存在 2 种不同路径长度（范围 1~3），体现路径长度分析的区分度
  - 非完全二叉树优先，增加树结构分析的复杂度
  - leaf_count 4~6 个叶子节点，权值为 1~15 的正整数且各不相同
  - 四选项间最小差值 ≥ 3，干扰项与正确值差 5~20
- should_not_be:
  - 不考哈夫曼树的构造过程
  - 不考 WPL 与编码效率的关系
  - 不考线索二叉树或遍历序列
  - 不出现负数权值或小数权值
  - 不出现完全二叉树（降低结构区分度）
- hard_constraints:
  - option_count: 4
  - condition_count: 2（条件1=二叉树完整结构；条件2=各叶子节点权值）
  - tree_depth: 3~4 层（根为第 0 层）
  - 路径长度定义：从根到节点的边数

## route

- question_form: single_choice
- question_type: computational
- requires_parameter_verification: true
- requires_solver: true
- requires_code: true

## core_knowledge_intent

- must_test:
  - WPL 公式的正确应用：WPL = Σ(叶子权值 × 根到该叶子的路径长度)
  - 路径长度的正确定义：从根到节点的边数（非层数、非节点数）
  - 从树结构中准确识别所有叶子节点并确定各自的路径长度
- must_not_shift_to:
  - 哈夫曼树构造或哈夫曼编码
  - 二叉树遍历（前/中/后/层序）作为独立考点
- coverage_success_criteria:
  - solver 能从给定树结构正确提取每个叶子节点的权值和路径长度
  - solver 能执行多步加权求和得到 WPL 正确值
  - 至少 3 个干扰项对应明确的认知错误算法，而非随机数值

## expected_reasoning_actions

1. 从给定的二叉树结构中识别所有叶子节点（度为 0 的节点）
2. 对每个叶子节点，确定从根到该叶子的路径长度（边的条数）
3. 将每个叶子的权值乘以其路径长度，得到各叶子的带权路径长度
4. 对所有叶子的带权路径长度求和，得到 WPL
5. 对比四个选项，排除干扰项（检查是否存在层数代替边数、遗漏叶子、内部节点误计等错误）

## question_structure_plan

### stem_style
给定一棵非完全二叉树的完整结构（通过图形或无歧义的结构描述）以及各叶子节点的权值，要求计算该二叉树的带权路径长度 WPL。四个选项供选择。

### option_architecture
- correct: 正确执行 WPL = Σ(权值 × 路径长度)，路径长度取边数
- distractor_1 — 路径长度偏移（层数与边数混淆）: 错误地用"层数"（根为第1层）代替"边数"作为路径长度，导致每个叶子的路径长度被整体偏移 +1
- distractor_2 — 遗漏叶子: 在求和时遗漏一个叶子节点（如遗漏最深层的某个叶子），导致 WPL 偏小
- distractor_3 — 内部节点误计: 将一个或多个内部（非叶）节点的权值也纳入 WPL 求和，导致 WPL 偏大

### asking_method
"该二叉树的带权路径长度 WPL 为（ ）。" 四选一。

### distractor_error_algorithms
- D1 (层数偏移): WPL_wrong = Σ(权值 × (路径长度 + 1))，即每个叶子的路径长度加 1
- D2 (遗漏叶子): WPL_wrong = WPL_correct - (遗漏叶子的权值 × 该叶子的路径长度)，选择一个对总和贡献显著的叶子遗漏
- D3 (内部节点误计): WPL_wrong = WPL_correct + Σ(误计内部节点权值 × 该节点路径长度)，选择一个或多个内部节点误纳入

## parameter_plan

### parameter_slots
- name: leaf_count
  role: 叶子节点数量
  candidate_range: 4~6
  used_by: 树结构生成、WPL 计算
- name: tree_depth
  role: 树的层数（根为第 0 层）
  candidate_range: 3~4
  used_by: 路径长度确定、树结构生成
- name: weights
  role: 各叶子节点的权值
  candidate_range: 1~15 的正整数，各不相同
  used_by: WPL 计算
- name: tree_shape
  role: 树的形态（非完全二叉树）
  candidate_range: 至少有一个内部节点只有一个孩子
  used_by: 路径长度分析区分度
- name: path_length_set
  role: 叶子节点路径长度的种类
  candidate_range: 至少 2 种不同路径长度，取值范围 1~3
  used_by: WPL 计算、干扰项生成

### validation_targets
- WPL_correct 为正整数
- 四个选项中仅一个等于 WPL_correct
- 四选项间最小差值 ≥ 3
- 每个干扰项与正确值差 5~20
- D1 (层数偏移) 结果与正确值之差 = leaf_count（因为每个叶子路径长度都多 1，差值 = Σ权值），该差值须在 5~20 范围内
- D2 (遗漏叶子) 结果与正确值之差 = 遗漏叶子的(权值 × 路径长度)，须在 5~20 范围内
- D3 (内部节点误计) 结果与正确值之差 = 误计内部节点的(权值 × 路径长度)，须在 5~20 范围内
- 所有四个选项互不相同

### adjustment_priority
1. 首先确定 leaf_count 和 tree_shape，保证非完全二叉树且有 ≥2 种路径长度
2. 分配 weights 使各权值不同且 D1 偏移量（Σ权值）落在 5~20
3. 验证 D2、D3 的偏移量均在 5~20，若不满足则调整权值或选择不同的遗漏/误计节点
4. 最终检查四选项最小间距 ≥ 3

## terminology_and_expression_constraints

### required_terms
- "带权路径长度" / "WPL"（题干中至少出现一次全称）
- "叶子节点"（不使用"终端节点""末端节点"等替代说法）
- "路径长度"（指从根到节点的边的条数）

### required_qualifiers
- 题干须注明"根为第 0 层"或等价表述，消除层数定义歧义
- 若用图形表示树结构，须标注各叶子节点的权值
- 选项格式为纯整数，不带单位

### avoid_phrases
- "节点的深度"（易与路径长度混淆，除非明确定义）
- "路径长度为节点数"（错误定义）

### standard_rewrites
- bad: "节点的层数即为路径长度"
  good: "从根到该节点的路径长度为所经过的边的条数"
- bad: "WPL 是所有节点的带权路径长度之和"
  good: "WPL 是所有叶子节点的带权路径长度之和"

## audit_focus

### final_review_must_check
- 路径长度定义是否与标准一致（边数，非层数、非节点数）
- 树结构是否为非完全二叉树，是否存在 ≥2 种不同路径长度
- leaf_count 是否在 4~6 范围内
- 权值是否为 1~15 的正整数且各不相同
- 四个选项是否互不相同，最小差值是否 ≥ 3
- 每个干扰项是否对应明确的错误算法（D1 层数偏移 / D2 遗漏叶子 / D3 内部节点误计），而非随机数值
- 题干是否包含"根为第 0 层"或等价限定语
- 不涉及哈夫曼树构造、编码效率、线索二叉树等超纲内容

### solve_output_should_contain
- solver 逐叶子列出权值和路径长度的中间过程
- WPL 正确值的计算式（如 WPL = w1×l1 + w2×l2 + ... ）
- 三个干扰项各自对应的错误算法说明及计算结果
- 四选项与正确值的差值验证（均在 5~20，最小间距 ≥ 3）

### fail_if_missing
- 缺少路径长度的明确定义（边数）
- 树为完全二叉树（缺乏路径长度分析区分度）
- 任一干扰项无法归因到明确错误算法
- 四选项间出现差值 < 3 的相邻项
- 涉及哈夫曼构造或编码内容
