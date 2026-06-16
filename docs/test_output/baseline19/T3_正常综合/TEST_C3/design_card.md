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
- should_be:
  - 需多步串行推演树的形态变化
  - 需精准辨析四种旋转类型的触发条件
- should_not_be:
  - 不得仅考查单一旋转的记忆
  - 不得出现无需推演即可排除的选项
- hard_constraints:
  - 必须通过插入操作触发旋转
  - 必须考查失衡判定与旋转类型的对应关系

## route

- question_form: single_choice
- question_type: mixed
- requires_parameter_verification: true
- requires_solver: true
- requires_code: true

## core_knowledge_intent

- must_test:
  - AVL 树插入操作后沿路径回溯检查平衡因子的过程
  - 四种旋转类型（LL/RR/LR/RL）的触发条件与执行方式
  - 旋转后子树高度变化对祖先节点平衡因子的影响
- must_not_shift_to:
  - 不得退化为纯概念辨析（如"什么是 AVL 树"）
  - 不得仅考查单次旋转的记忆而不涉及插入推演
- coverage_success_criteria:
  - 学生必须完整模拟从插入到旋转恢复平衡的全过程
  - 学生必须能区分四种旋转的触发条件并正确执行

## expected_reasoning_actions

- 将给定关键字按二叉排序树规则插入到当前 AVL 树中
- 从插入节点沿父指针回溯至根，逐节点计算并更新平衡因子
- 识别第一个平衡因子绝对值超过 1 的失衡节点
- 根据失衡节点与其子节点、孙节点的相对位置关系，判定旋转类型（LL/RR/LR/RL）
- 执行对应旋转操作，更新节点指针关系
- 检查旋转后祖先节点的平衡因子是否仍需调整
- 确定最终树结构或旋转后的关键状态

## question_structure_plan

- stem_style: 给定初始 AVL 树结构 + 插入关键字序列，要求判断插入完成后的树状态
- asking_method: 单选题，设问指向插入操作完成后的某个具体状态（如根节点、某子树形态、旋转次数等）
- option_architecture:
  - correct: 完整正确模拟插入+旋转后的结果
  - distractor_1 (概念混淆): 旋转类型判断错误（如将 LR 误判为 LL），导致旋转方向错误
  - distractor_2 (中间值): 仅完成插入未执行旋转，或仅执行了部分旋转的中间状态
  - distractor_3 (条件遗漏): 旋转后未继续回溯检查祖先节点平衡因子，遗漏二次旋转
- distractor_strategies_selected:
  - 概念混淆：相似旋转类型替换（LL↔LR 或 RR↔RL）
  - 中间值：计算过程中的中间树形态当作最终答案
  - 条件遗漏：忽略旋转后需继续回溯检查祖先节点的约束

## parameter_plan

- parameter_slots:
  - slot_name: initial_avl_tree
    role: 初始 AVL 树结构（节点数、关键字分布、树高）
    candidate_range: 5-8 个节点，树高 3-4，确保插入后能触发旋转
    used_by: 题干、求解验证
  - slot_name: insertion_key
    role: 待插入的关键字
    candidate_range: 与初始树关键字不重复的整数，插入后能导致失衡
    used_by: 题干、求解验证
  - slot_name: insertion_sequence
    role: 可选的多关键字插入序列
    candidate_range: 2-3 个关键字，按顺序插入
    used_by: 题干（若采用序列插入模式）
- validation_targets:
  - 初始树必须是合法的 AVL 树（所有节点平衡因子 ∈ {-1, 0, 1}）
  - 插入操作必须触发至少一次旋转
  - 旋转类型必须唯一确定（不存在多种旋转路径）
  - 正确答案与三个干扰项必须可区分
  - 干扰项对应的错误路径必须是合理的认知错误（非随机构造）
- adjustment_priority:
  - 优先调整 insertion_key 确保触发旋转
  - 其次调整 initial_avl_tree 确保树结构复杂度适中
  - 最后微调参数确保干扰项与正确答案的区分度

## terminology_and_expression_constraints

- required_terms:
  - 平衡二叉树 / AVL 树
  - 平衡因子
  - 左旋 / 右旋 / 左-右旋 / 右-左旋（或 LL/RR/LR/RL 旋转）
  - 失衡节点 / 最小不平衡子树
- required_qualifiers:
  - 描述旋转时必须说明"以某节点为根的子树"
  - 描述平衡因子时必须说明"左子树高度减右子树高度"
  - 描述插入时必须说明"按二叉排序树规则插入"
- avoid_phrases:
  - "调整"（过于模糊，应明确为"旋转"）
  - "平衡操作"（应明确为具体旋转类型）
  - "重新平衡"（应描述具体旋转过程）
- standard_rewrites:
  - bad: "对树进行调整" → good: "执行左-右旋（LR 旋转）"
  - bad: "树不平衡了" → good: "节点 X 的平衡因子变为 -2，成为失衡节点"
  - bad: "旋转一下" → good: "以节点 Y 为根执行右旋操作"

## audit_focus

- final_review_must_check:
  - 初始 AVL 树结构是否合法（所有节点平衡因子 ∈ {-1, 0, 1}）
  - 插入操作是否确实触发旋转（非插入即平衡的情况）
  - 旋转类型判定是否唯一（不存在歧义）
  - 四个选项是否覆盖"正确答案 + 3 种不同错误认知路径"
  - 干扰项是否对应设计卡中选定的干扰策略（概念混淆/中间值/条件遗漏）
  - 题干是否明确说明插入规则（按 BST 规则）
  - 设问是否指向可唯一确定的状态
- solve_output_should_contain:
  - 初始树的平衡因子标注
  - 插入后的树结构及平衡因子更新过程
  - 失衡节点的定位过程
  - 旋转类型判定依据
  - 旋转后的最终树结构
  - 正确答案的数值/结构描述
  - 三个干扰项对应的错误路径说明
- fail_if_missing:
  - 初始树不是合法 AVL 树
  - 插入后未触发任何旋转
  - 旋转类型存在歧义（多种旋转路径均可）
  - 干扰项与正确答案无法区分
  - 缺少任一选定干扰策略对应的干扰项
