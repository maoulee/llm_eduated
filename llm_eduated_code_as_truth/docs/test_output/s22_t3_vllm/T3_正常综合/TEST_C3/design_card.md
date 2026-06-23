## status

draft

## blueprint_contract

- slot_id: Q41
- question_type: 选择题
- score: 2
- target_subject: 数据结构
- target_family: 树与二叉树
- primary_target_name: 平衡二叉树 AVL
- examination_mode: 结构操作与状态维护模拟
- k_target: K3-K4平衡型
- difficulty_level: 4
- should_be: 需多步串行推演树的形态变化
- should_be: 需精准辨析四种旋转类型的触发条件
- should_not_be: （蓝图未明确列出）
- hard_constraints: 推演步数 >5 步或需维持动态状态更新；隐含前提深，需依靠对机制本质的理解才能路由

## route

- question_form: single_choice
- question_type: mixed
- requires_parameter_verification: true
- requires_solver: true
- requires_code: true

## core_knowledge_intent

- must_test:
  - AVL 树插入操作的完整流程（查找插入位置 → 插入节点 → 回溯更新平衡因子 → 判断失衡 → 执行旋转）
  - 四种旋转类型（LL/RR/LR/RL）的触发条件与平衡因子变化规律
  - 插入后树形态的动态维护与平衡因子重新计算
- must_not_shift_to:
  - 纯概念记忆题（如"AVL 树定义是什么"）
  - 仅考察单次旋转的孤立操作（脱离插入流程）
- coverage_success_criteria:
  - 学生需完整模拟至少 3 次插入操作，其中至少触发 2 种不同类型的旋转
  - 最终树结构必须为合法 AVL 树，且所有节点平衡因子 ∈ {-1, 0, 1}

## design_rationale

本题通过"给定初始 AVL 树 + 插入序列 → 求最终树结构"的设问方式，考察学生在多步串行推演中维持树状态的能力。选择这个考点组合（插入流程 + 旋转类型辨析 + 平衡因子计算）是因为：单一考察旋转名称或平衡因子定义只能区分记忆水平，而将三者融合在插入模拟中，才能区分"能完整走完旋转流程并回溯检查的学生"与"只记得旋转名称但无法在动态变化中正确路由的学生"。K3-K4 平衡型的设计意图是：K3 要求学生按 AVL 插入规则走完 >5 步流程（插入→回溯→判断→旋转→再回溯），K4 要求学生在每一步识别隐含前提（如"插入后需从插入点回溯至根检查平衡因子"、"双旋转时需先旋子节点再旋父节点"），这些隐含前提题面不会明说，但解题必须意识到。选择题形式适合 408 考研数据结构部分的题量节奏，同时通过精心设计的干扰项（对应常见认知错误路径）进一步区分掌握程度。

## expected_reasoning_actions

- 从初始 AVL 树I have to give the solution based on the reasoning directly now.</think>

## status

draft

## blueprint_contract

- slot_id: Q41
- question_type: 选择题
- score: 2
- target_subject: 数据结构
- target_family: 树与二叉树
- primary_target_name: 平衡二叉树 AVL
- examination_mode: 结构操作与状态维护模拟
- k_target: K3-K4平衡型
- difficulty_level: 4
- should_be: 需多步串行推演树的形态变化
- should_be: 需精准辨析四种旋转类型的触发条件
- should_not_be: （蓝图未明确列出）
- hard_constraints: 推演步数 >5 步或需维持动态状态更新；隐含前提深，需依靠对机制本质的理解才能路由

## route

- question_form: single_choice
- question_type: mixed
- requires_parameter_verification: true
- requires_solver: true
- requires_code: true

## core_knowledge_intent

- must_test:
  - AVL 树插入操作的完整流程（查找插入位置 → 插入节点 → 回溯更新平衡因子 → 判断失衡 → 执行旋转）
  - 四种旋转类型（LL/RR/LR/RL）的触发条件与平衡因子变化规律
  - 插入后树形态的动态维护与平衡因子重新计算
- must_not_shift_to:
  - 纯概念记忆题（如"AVL 树定义是什么"）
  - 仅考察单次旋转的孤立操作（脱离插入流程）
- coverage_success_criteria:
  - 学生需完整模拟至少 3 次插入操作，其中至少触发 2 种不同类型的旋转
  - 最终树结构必须为合法 AVL 树，且所有节点平衡因子 ∈ {-1, 0, 1}

## design_rationale

本题通过"给定初始 AVL 树 + 插入序列 → 求最终树结构"的设问方式，考察学生在多步串行推演中维持树状态的能力。选择这个考点组合（插入流程 + 旋转类型辨析 + 平衡因子计算）是因为：单一考察旋转名称或平衡因子定义只能区分记忆水平，而将三者融合在插入模拟中，才能区分"能完整走完旋转流程并回溯检查的学生"与"只记得旋转名称但无法在动态变化中正确路由的学生"。K3-K4 平衡型的设计意图是：K3 要求学生按 AVL 插入规则走完 >5 步流程（插入→回溯→判断→旋转→再回溯），K4 要求学生在每一步识别隐含前提（如"插入后需从插入点回溯至根检查平衡因子"、"双旋转时需先旋子节点再旋父节点"），这些隐含前提题面不会明说，但解题必须意识到。选择题形式适合 408 考研数据结构部分的题量节奏，同时通过精心设计的干扰项（对应常见认知错误路径）进一步区分掌握程度。

## expected_reasoning_actions

- 从初始 AVL 树出发，逐个插入给定序列中的节点
- 每次插入后，从插入位置回溯至根节点，逐层更新平衡因子
- 识别平衡因子绝对值超过 1 的失衡节点
- 根据失衡节点与其子节点的平衡因子关系，判断旋转类型（LL/RR/LR/RL）
- 执行对应旋转操作，更新树结构
- 旋转后继续回溯检查祖先节点是否仍平衡
- 重复上述流程直至所有节点插入完毕
- 输出最终 AVL 树的形态（或关键特征，如根节点、某层节点集合等）

## question_structure_plan

- stem_style: 给定初始 AVL 树结构（图形或层序描述）+ 插入序列，求插入全部节点后的最终树结构
- asking_method: 直接询问最终 AVL 树的形态（如根节点值、某层节点集合、或完整树结构的图形选项）
- option_architecture:
  - correct: 正确执行全部插入与旋转后的最终 AVL 树结构
  - distractor_1（概念混淆）：混淆 LL 与 LR 旋转触发条件，导致旋转类型判断错误，树结构偏离正确结果
  - distractor_2（偏移错误/中间值）：仅执行部分插入操作或遗漏某次旋转，输出中间状态的树结构
  - distractor_3（条件遗漏）：旋转后未回溯检查祖先节点平衡因子，遗漏二次旋转，树结构不满足 AVL 性质
- distractor_strategy_selected:
  - 概念混淆：LL/LR 或 RR/RL 旋转条件张冠李戴
  - 中间值：计算过程中的中间树结构当作最终答案
  - 条件遗漏：忽略旋转后需回溯检查祖先节点的隐含前提

## parameter_plan

- parameter_slots:
  - initial_avl_tree: 初始 AVL 树结构（节点值集合 + 父子关系），候选范围：5-8 个节点的合法 AVL 树
  - insertion_sequence: 插入节点值序列，候选范围：3-5 个整数，需确保触发至少 2 种不同类型的旋转
  - final_tree_structure: 插入全部节点后的最终 AVL 树结构（由 initial_avl_tree + insertion_sequence 推导得出）
- validation_targets:
  - 初始树必须是合法 AVL 树（所有节点平衡因子 ∈ {-1, 0, 1}）
  - 插入序列必须触发至少 2 种不同类型的旋转（如 LL + LR，或 RR + RL）
  - 最终树必须是合法 AVL 树
  - 4 个选项（1 正确 + 3 干扰）必须互不相同
  - 每个干扰项必须对应选定的干扰策略，且可由常见错误路径推导得出
- adjustment_priority:
  - 优先调整 insertion_sequence 以确保触发多种旋转类型
  - 其次调整 initial_avl_tree 以控制推演步数在合理范围（>5 步但不过于冗长）
  - 最后微调节点值以区分选项

## terminology_and_expression_constraints

- required_terms:
  - 平衡二叉排序树 / AVL 树
  - 平衡因子
  - 左旋 / 右旋
  - LL 型 / RR 型 / LR 型 / RL 型（或"左左型/右右型/左右型/右左型"）
  - 失衡节点
- required_qualifiers:
  - 平衡因子定义必须明确为"左子树高度 − 右子树高度"（或明确说明采用的定义）
  - 旋转类型命名需与平衡因子定义一致
- avoid_phrases:
  - "旋转方向"（模糊，应明确为"左旋/右旋"）
  - "失衡"（单独使用易歧义，应写为"平衡因子绝对值超过 1"）
  - "调整"（应明确为"执行 LL/RR/LR/RL 旋转"）
- standard_rewrites:
  - bad: "对失衡节点进行旋转" → good: "对平衡因子绝对值超过 1 的节点执行对应类型的旋转（LL/RR/LR/RL）"
  - bad: "旋转后树就平衡了" → good: "旋转后需从旋转点继续回溯至根，检查祖先节点平衡因子"

## audit_focus

- final_review_must_check:
  - 初始 AVL 树为合法 AVL 树（所有节点平衡因子 ∈ {-1, 0, 1}）
  - 插入序列确实触发至少 2 种不同类型的旋转
  - 最终树结构为合法 AVL 树
  - 4 个选项互不相同，且正确选项唯一
  - 3 个干扰项分别对应 question_structure_plan 中选定的 3 种干扰策略
  - 题干表述无歧义，平衡因子定义与旋转类型命名一致
- solve_output_should_contain:
  - 初始 AVL 树的完整结构描述（节点值 + 父子关系 + 平衡因子）
  - 每次插入操作的详细过程（插入位置、回溯路径、平衡因子更新）
  - 每次旋转的触发条件、旋转类型、旋转前后树结构对比
  - 最终 AVL 树的完整结构描述
  - 4 个选项的生成依据（正确选项推导 + 3 个干扰项对应的错误路径）
- fail_if_missing:
  - 缺少旋转过程描述（只有最终结果无中间步骤）
  - 最终树结构不满足 AVL 性质（存在平衡因子绝对值 > 1 的节点）
  - 干扰项无法对应到选定的干扰策略
  - 插入序列未触发多种旋转类型（仅触发 1 种或 0 种）
  - 选项之间存在重复或正确选项不唯一
