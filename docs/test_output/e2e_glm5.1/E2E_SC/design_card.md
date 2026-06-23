# Design Card — 二叉树带权路径长度(WPL)

## status

draft

## blueprint_contract

- slot_id: (待分配)
- question_type: single_choice
- score: 2
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度(WPL)
- examination_mode: 给定权值集合构造哈夫曼树并计算WPL
- k_target: K1=3, K2=2, K3=3, K4=2, K5=2
- difficulty_level: 3
- should_be:
  - 核心考察哈夫曼树构造过程与WPL计算
  - 路径长度定义为常见易错点，需体现区分度
  - 每个干扰项对应一个明确的常见计算错误
  - 叶子节点数 n 在 5~7 范围内
  - 权值集合中至少有一对相近值增加构造判断难度
  - 四个选项值互不相同
  - 答案位置 A/B/C/D 随机分布
- should_not_be:
  - 不考察哈夫曼编码的具体编码方案
  - 不涉及平衡二叉树或二叉搜索树内容
  - 不出现超出 n=7 的权值集合
  - 不出现单个权值超过 15 的取值
- hard_constraints:
  - 正确WPL值由权值集合和哈夫曼构造唯一确定，不可自由设定
  - 每个干扰项偏差范围 ±2~±5
  - 权值 wᵢ 均为正整数，1 ≤ wᵢ ≤ 15

## route

- question_form: single_choice
- question_type: computational
- requires_parameter_verification: true
- requires_solver: true
- requires_code: true

## core_knowledge_intent

- must_test:
  - 哈夫曼树的构造过程：每次选两个最小权值合并，重复合并直到只剩一棵树
  - WPL 的定义与计算：每个叶子权值 × 该叶子到根的路径长度（边数），所有叶子求和
  - 在存在相近权值时，构造过程中正确选择最小两值的判断能力
- must_not_shift_to:
  - 不偏移到哈夫曼编码（前缀编码、编码长度等）
  - 不偏移到树的遍历或二叉树其他性质（深度、度数统计等）
- coverage_success_criteria:
  - 学生能完整走完哈夫曼树构造流程并正确累加每个叶子的带权路径长度
  - 学生能区分"路径长度 = 边数"而非"路径长度 = 节点数"，体现对定义的精确掌握

## design_rationale

本题考察"哈夫曼树构造 + WPL 计算"这一经典组合，核心意图是区分**能完整执行哈夫曼构造流程并精确计算 WPL 的学生**与**只记得概念名称但无法准确操作的学生**。选择 n=5~7 的权值集合，使得构造过程需要 2~3 轮合并、存在相近权值需要判断，既有计算量又不至于繁琐。K1=3（知识广度）和 K3=3（计算推理）双高，K2=2（概念辨析）中等——说明本题不以概念辨析为主战场，而是用计算过程的正确性来筛选。三个干扰项分别对应三种最典型的系统性错误（路径长度用节点数代替边数、哈夫曼构造顺序错误、遗漏部分叶子节点），每种错误都产生可追溯的偏差值，这样错误选项不是随机数值，而是真实反映认知缺陷的"诊断型"干扰。难度定位 3 级合适：权值规模适中、计算路径清晰但需要精确执行，适合在选择题题位区分中等水平学生。

## expected_reasoning_actions

- 从给定权值集合中选出两个最小权值，合并为新节点，重复此过程直到完成哈夫曼树构造
- 在存在相近权值时，正确判断每轮合并应选取的两个最小值（区分相近值的大小关系）
- 逐个叶子节点计算其到根的路径长度（经过的边数），乘以权值得到该叶子的带权路径长度
- 将所有叶子节点的带权路径长度累加，得到最终 WPL
- 对照四个选项，验证哪个选项与正确计算结果一致

## question_structure_plan

- stem_style: 给定 n 个正整数权值，要求构造哈夫曼树并求 WPL
- option_architecture:
  - correct: 正确构造哈夫曼树后精确计算的 WPL 值
  - distractor_1（偏移错误 — 路径长度定义混淆）: 每个叶子的路径长度按"节点数"（=边数+1）计算，导致 WPL 系统性偏大，偏差 = 叶子节点数 n
  - distractor_2（哈夫曼构造顺序错误）: 构造过程中某轮未选严格最小的两个权值（因相近值混淆），导致生成的树非最优，WPL 偏大或偏小
  - distractor_3（非叶节点纳入 / 遗漏叶子节点）: 计算时遗漏一个或多个叶子节点的贡献，导致 WPL 偏小，偏差 = 遗漏叶子的带权路径长度
- asking_method: "该哈夫曼树的带权路径长度(WPL)为"
- 答案位置: A/B/C/D 随机分布，不固定

## parameter_plan

- parameter_slots:
  - name: n
    role: 叶子节点数（权值集合大小）
    candidate_range: 5 ≤ n ≤ 7
    used_by: 哈夫曼树构造轮数、WPL 累加项数
  - name: weights
    role: 权值集合 {w₁, ..., wₙ}
    candidate_range: 每个wᵢ为正整数，1 ≤ wᵢ ≤ 15；集合中至少有一对差值 ≤ 2 的相近值
    used_by: 哈夫曼构造顺序判断、WPL 计算
  - name: correct_wpl
    role: 正确 WPL 值
    candidate_range: 由 weights 和哈夫曼构造唯一确定
    used_by: 正确选项
  - name: distractor_values
    role: 三个干扰项的数值
    candidate_range: 每个干扰项与正确值的偏差在 ±2~±5 范围内；四个选项值互不相同
    used_by: 三个干扰选项
- validation_targets:
  - 正确 WPL 值必须由给定的权值集合经标准哈夫曼构造唯一确定
  - distractor_1（路径长度用节点数）的偏差必须等于 n（叶子节点数）
  - distractor_2（构造顺序错误）的偏差必须可追溯到具体哪轮选错了值
  - distractor_3（遗漏叶子）的偏差必须等于被遗漏叶子的带权路径长度
  - 四个选项值互不相同
  - 权值集合中确实存在至少一对相近值
- adjustment_priority:
  - 1. 确保 weights 中存在相近值对
  - 2. 确保正确 WPL 与三个干扰项偏差均在 ±2~±5
  - 3. 确保 n 在 5~7 范围
  - 4. 确保答案位置随机分布

## terminology_and_expression_constraints

- required_terms:
  - "哈夫曼树"（不写"赫夫曼树"或"Huffman树"，以"哈夫曼树"为准）
  - "带权路径长度"或"WPL"
  - "权值"
- required_qualifiers:
  - 路径长度需明确为"从叶子到根的路径上的边数"，题干中可不显式说明但干扰项设计须以此为标准
  - 权值集合需明确为"n 个叶子的权值"
- avoid_phrases:
  - "最优二叉树"（可作为同义词提及但设问用"哈夫曼树"）
  - "编码"相关表述（避免暗示考察哈夫曼编码）
- standard_rewrites:
  - bad: "求该树的最小权值"
    good: "求该哈夫曼树的带权路径长度(WPL)"
  - bad: "每个节点的路径长度"
    good: "每个叶子节点到根的路径长度（边数）"

## audit_focus

- final_review_must_check:
  - 正确 WPL 是否确实由给定权值集合经标准哈夫曼构造唯一确定（需要 solver 验证）
  - 三个干扰项是否各自对应可解释的常见错误路径，偏差值在 ±2~±5 范围
  - 权值集合中是否确实存在至少一对相近值（差值 ≤ 2）
  - 四个选项值是否互不相同
  - 答案位置是否随机分布（不固定在某个位置）
  - 题干是否未出现哈夫曼编码相关暗示
- solve_output_should_contain:
  - 完整的哈夫曼树构造过程（每轮选哪两个权值、合并结果）
  - 每个叶子节点的路径长度（边数）和对应的带权路径长度
  - WPL 累加结果
  - 三个干扰项的具体计算方式与偏差来源解释
- fail_if_missing:
  - WPL 计算未基于标准哈夫曼构造流程
  - 干扰项偏差不在 ±2~±5 范围或不可解释
  - 权值集合无相近值对
  - 四个选项出现重复值
  - 题干涉及哈夫曼编码内容
