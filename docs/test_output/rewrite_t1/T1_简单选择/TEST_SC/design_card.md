## status
draft

## blueprint_contract
- slot_id: (待分配)
- question_type: single_choice
- score: (待分配)
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度
- examination_mode: 给定权值集合求哈夫曼树WPL
- k_target: K1=3,K2=3,K3=3,K4=2,K5=2
- difficulty_level: 3
- should_be:
  - 权值数量 n ∈ [4, 6]，建议5个
  - 每个权值 wᵢ ∈ [1, 50] 正整数
  - 避免全部权值相等，可含1-2对相等权值
  - 合并轮数 2-3 轮
  - WPL 结果范围建议在 50-200 之间
  - 干扰项与正确答案差距建议 10-30
- should_not_be:
  - 权值全部相等
  - 合并轮数少于 2 轮或多于 3 轮
  - WPL 结果超出 50-200 范围
  - 干扰项与正确答案差距过小（<10）或过大（>30）
- hard_constraints:
  - 选项数量：4
  - 条件数量：1

## route
- question_form: single_choice
- question_type: computational
- requires_parameter_verification: true
- requires_solver: true
- requires_code: false

## core_knowledge_intent
- must_test:
  - 哈夫曼树构造的贪心策略：每次选取权值最小的两个节点合并
  - 带权路径长度（WPL）的定义与计算：仅对叶子节点求和，WPL = Σ(权值 × 路径长度)
  - 路径长度的定义：从根节点到该节点所经过的边数
- must_not_shift_to:
  - 一般二叉树的遍历操作（前序/中序/后序）
  - 非哈夫曼树的其他树结构（如 AVL、红黑树）
- coverage_success_criteria:
  - 学生能正确执行 2-3 轮哈夫曼合并过程
  - 学生能准确识别叶子节点并计算 WPL，不将内部节点计入

## design_rationale
本题考察哈夫曼树构造与 WPL 计算的核心能力，采用"给定权值集合求 WPL"这一 408 真题高频模式（2015、2018 等年份反复出现），确保考察内容与考试实际高度对齐。选择 5 个权值、2-3 轮合并的设计，使计算量适中（K4=2），同时要求学生完整执行贪心合并流程（K1=3、K2=3、K3=3），形成"中等记忆+中等理解+中等应用+低计算+低综合"的 K-雷达形状。这种设计能有效区分两类学生：一类能完整走完哈夫曼构造流程并正确回溯计算 WPL 的学生，另一类仅记住"哈夫曼树"名称但无法执行合并步骤或混淆 WPL 计算范围的学生。选择题形式配合三类典型干扰（计算错误、构造错误、概念错误），可在不增加阅卷负担的前提下精准诊断学生的认知薄弱点。

## expected_reasoning_actions
- 将给定的权值集合按从小到大排序
- 每次从当前节点集合中选取权值最小的两个节点
- 将选中的两个节点合并为一个新节点，新节点权值为两子节点权值之和
- 将新节点加入集合，重复上述过程直到只剩一个根节点
- 识别哈夫曼树中的所有叶子节点（原始权值对应的节点）
- 计算每个叶子节点的路径长度（从根到该节点的边数）
- 对每个叶子节点计算 权值 × 路径长度，并求和得到 WPL

## question_structure_plan
- stem_style: 直接计算型——题干给出权值集合，直接问 WPL 的值
- asking_method: 给定 n 个权值，求以此构造的哈夫曼树的带权路径长度
- option_architecture:
  - correct: 正确 WPL 值
  - distractor_1 (计算错误-漏加合并权值): 在合并过程中遗漏某次合并产生的权值累加，导致 WPL 偏小
  - distractor_2 (构造错误-未按最小权值合并): 未严格遵循贪心策略，错误地选取非最小权值进行合并，导致树结构不同、WPL 偏大
  -I have to give the solution based on the reasoning directly now.</think>

## terminology_and_expression_constraints
- required_terms:
  - 哈夫曼树（Huffman Tree）
  - 带权路径长度（WPL）
  - 叶子节点（叶结点）
  - 路径长度
  - 权值
- required_qualifiers:
  - 必须明确"带权路径长度"是对**叶子节点**求和
  - 必须明确"路径长度"是从**根节点到该节点**的边数
  - 必须明确哈夫曼树构造采用**贪心策略**（每次选最小两个）
- avoid_phrases:
  - "节点的路径长度"（歧义：未说明是叶子还是所有节点）
  - "树的深度"（与路径长度概念不同）
  - "层数"（与路径长度定义不一致）
- standard_rewrites:
  - bad: "求该树的带权路径长度" → good: "求以此权值集合构造的哈夫曼树的带权路径长度（WPL）"
  - bad: "路径长度为从根到该节点的层数" → good: "路径长度为从根节点到该节点所经过的边数"

## audit_focus
- final_review_must_check:
  - 权值集合是否满足约束：n ∈ [4,6]，每个 wᵢ ∈ [1,50]，非全相等，可含1-2对相等
  - 哈夫曼合并过程是否恰好 2-3 轮
  - WPL 结果是否在 50-200 范围内
  - 4 个选项是否分别对应：1 个正确答案 + 3 类干扰（计算错误/构造错误/概念错误）
  - 干扰项与正确答案的差距是否在 10-30 之间
  - 题干是否明确限定"哈夫曼树"和"叶子节点"
- solve_output_should_contain:
  - 完整的哈夫曼树构造过程（每轮合并的两个节点权值及新节点权值）
  - 最终哈夫曼树的结构描述（或每轮合并记录）
  - 每个叶子节点的权值、路径长度、权值×路径长度的明细
  - WPL 的最终计算结果
  - 对每个干扰项的错误归因说明
- fail_if_missing:
  - 缺少哈夫曼合并过程的逐步记录
  - 未区分叶子节点与内部节点
  - WPL 计算结果不在 50-200 范围内
  - 干扰项未覆盖三类典型错误中的至少两类
  - 题干未明确"哈夫曼树"或"叶子节点"限定条件
