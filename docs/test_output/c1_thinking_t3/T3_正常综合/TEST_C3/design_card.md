## status
draft

## blueprint_contract
slot_id: Q41
question_type: 选择题
score: 2
target_subject: 数据结构
target_family: 树与二叉树
primary_target_name: 平衡二叉树 AVL
examination_mode: 结构操作与状态维护模拟
k_target: K3-K4平衡型
difficulty_level: 4
should_be:
- 需多步串行推演树的形态变化
- 需精准辨析四种旋转类型的触发条件
should_not_be:
hard_constraints:

## route
question_form: single_choice
question_type: mixed
requires_parameter_verification: true
requires_solver: true
requires_code: true

## core_knowledge_intent
must_test:
- AVL 树插入操作后平衡因子的逐层更新与失衡结点定位
- 四种旋转类型（LL/RR/LR/RL）的触发条件判断与正确执行
- 旋转操作后树结构的正确更新与 AVL 性质验证

must_not_shift_to:
- 仅考察 BST 插入而不涉及平衡调整
- 仅记忆旋转名称而不理解触发条件与执行过程

coverage_success_criteria:
- 学生能完整模拟从插入到旋转的全流程，并正确判断旋转类型
- 学生能准确计算插入后各结点的平衡因子并验证 AVL 性质

## design_rationale
本题考察 AVL 树插入与旋转的完整流程，选择"结构操作与状态维护模拟"模式是因为 AVL 树的核心能力不在于记忆旋转名称，而在于能在动态插入过程中维持平衡状态。K3-K4 平衡型的设计意图是：K3 要求学生按固定规则走完"插入→更新平衡因子→定位失衡结点→判断旋转类型→执行旋转→验证性质"的多步流程（>5步），K4 要求学生识别隐含前提——如 LR/RL 型需要先对子结点旋转再对失衡结点旋转、旋转后需重新计算所有受影响结点的平衡因子。这种设计要区分的是"能完整走完旋转流程并回溯检查的学生"与"只记得旋转名称但无法在动态插入中正确判断触发条件的学生"。选择题形式配合多步推演，既能控制答题时间，又能通过干扰项精准捕捉常见认知错误路径（如未执行旋转、旋转类型判断错误、平衡因子计算错误）。

## expected_reasoning_actions
- 在初始 AVL 树中按 BST 规则定位新结点的插入位置
- 从插入结点沿父指针逐层向上更新各结点的平衡因子
- 定位第一个平衡因子绝对值超过 1 的失衡结点
- 根据失衡结点与其子结点、孙结点的平衡因子关系判断旋转类型（LL/RR/LR/RL）
- 执行对应旋转操作并更新树结构
- 重新计算旋转后所有受影响结点的平衡因子
- 验证旋转后整棵树是否满足 AVL 性质（所有结点平衡因子 ∈ {-1, 0, 1}）

## question_structure_plan
stem_style: 给出初始 AVL 树结构（图形或关键字序列描述）+ 待插入的关键字 → 询问插入后树的某种属性
asking_method: 询问插入操作完成后树的某个具体属性（如根结点关键字、某结点平衡因子、旋转类型、旋转次数等）
option_architecture:
  correct: 完整模拟插入+旋转流程后的正确结果
  distractor_1: 未执行旋转操作（仅 BST 插入）导致的结果
  distractor_2: 旋转类型判断错误（如将 LR 型误判为 LL 型）导致的结果
  distractor_3: 平衡因子计算错误（如符号错误或遗漏更新）导致的结果

## parameter_plan
parameter_slots:
  - name: initial_avl_tree
    role: 初始 AVL 树结构
    candidate_range: 3-5 个结点的合法 AVL 树，确保插入后触发旋转
    used_by: 题干描述
  - name: insert_key
    role: 待插入的关键字
    candidate_range: 与初始树关键字不重复的整数，插入后至少触发一次旋转
    used_by: 题干描述
  - name: query_target
    role: 设问目标属性
    candidate_range: 根结点关键字 / 某结点平衡因子 / 旋转类型 / 旋转次数
    used_by: 设问

validation_targets:
  - 初始树必须是合法的 AVL 树（所有结点平衡因子 ∈ {-1, 0, 1}）
  - 插入后必须触发至少一次旋转
  - 旋转后树必须满足 AVL 性质
  - 四个选项必须互不相同
  - 干扰项必须对应明确的错误认知路径

adjustment_priority:
  1. 确保插入后触发旋转（否则降低 K3 推演需求）
  2. 确保旋转类型判断有区分度（避免仅 LL/RR 型过于简单）
  3. 确保干扰项对应真实认知错误

## terminology_and_expression_constraints
required_terms:
- 平衡因子（balance factor）
- 左旋（left rotation）
- 右旋（right rotation）
- LL型 / RR型 / LR型 / RL型
I have to give the solution based on the reasoning directly now.</think>

## status
draft

## blueprint_contract
slot_id: Q41
question_type: 选择题
score: 2
target_subject: 数据结构
target_family: 树与二叉树
primary_target_name: 平衡二叉树 AVL
examination_mode: 结构操作与状态维护模拟
k_target: K3-K4平衡型
difficulty_level: 4
should_be:
- 需多步串行推演树的形态变化
- 需精准辨析四种旋转类型的触发条件
should_not_be:
hard_constraints:

## route
question_form: single_choice
question_type: mixed
requires_parameter_verification: true
requires_solver: true
requires_code: true

## core_knowledge_intent
must_test:
- AVL 树插入操作后平衡因子的逐层更新与失衡结点定位
- 四种旋转类型（LL/RR/LR/RL）的触发条件判断与正确执行
- 旋转操作后树结构的正确更新与 AVL 性质验证

must_not_shift_to:
- 仅考察 BST 插入而不涉及平衡调整
- 仅记忆旋转名称而不理解触发条件与执行过程

coverage_success_criteria:
- 学生能完整模拟从插入到旋转的全流程，并正确判断旋转类型
- 学生能准确计算插入后各结点的平衡因子并验证 AVL 性质

## design_rationale
本题考察 AVL 树插入与旋转的完整流程，选择"结构操作与状态维护模拟"模式是因为 AVL 树的核心能力不在于记忆旋转名称，而在于能在动态插入过程中维持平衡状态。K3-K4 平衡型的设计意图是：K3 要求学生按固定规则走完"插入→更新平衡因子→定位失衡结点→判断旋转类型→执行旋转→验证性质"的多步流程（>5步），K4 要求学生识别隐含前提——如 LR/RL 型需要先对子结点旋转再对失衡结点旋转、旋转后需重新计算所有受影响结点的平衡因子。这种设计要区分的是"能完整走完旋转流程并回溯检查的学生"与"只记得旋转名称但无法在动态插入中正确判断触发条件的学生"。选择题形式配合多步推演，既能控制答题时间，又能通过干扰项精准捕捉常见认知错误路径（如未执行旋转、旋转类型判断错误、平衡因子计算错误）。

## expected_reasoning_actions
- 在初始 AVL 树中按 BST 规则定位新结点的插入位置
- 从插入结点沿父指针逐层向上更新各结点的平衡因子
- 定位第一个平衡因子绝对值超过 1 的失衡结点
- 根据失衡结点与其子结点、孙结点的平衡因子关系判断旋转类型（LL/RR/LR/RL）
- 执行对应旋转操作并更新树结构
- 重新计算旋转后所有受影响结点的平衡因子
- 验证旋转后整棵树是否满足 AVL 性质（所有结点平衡因子 ∈ {-1, 0, 1}）

## question_structure_plan
stem_style: 给出初始 AVL 树结构（图形或关键字序列描述）+ 待插入的关键字 → 询问插入后树的某种属性
asking_method: 询问插入操作完成后树的某个具体属性（如根结点关键字、某结点平衡因子、旋转类型、旋转次数等）
option_architecture:
  correct: 完整模拟插入+旋转流程后的正确结果
  distractor_1: 未执行旋转操作（仅 BST 插入）导致的结果
  distractor_2: 旋转类型判断错误（如将 LR 型误判为 LL 型）导致的结果
  distractor_3: 平衡因子计算错误（如符号错误或遗漏更新）导致的结果

## parameter_plan
parameter_slots:
  - name: initial_avl_tree
    role: 初始 AVL 树结构
    candidate_range: 3-5 个结点的合法 AVL 树，确保插入后触发旋转
    used_by: 题干描述
  - name: insert_key
    role: 待插入的关键字
    candidate_range: 与初始树关键字不重复的整数，插入后至少触发一次旋转
    used_by: 题干描述
  - name: query_target
    role: 设问目标属性
    candidate_range: 根结点关键字 / 某结点平衡因子 / 旋转类型 / 旋转次数
    used_by: 设问

validation_targets:
  - 初始树必须是合法的 AVL 树（所有结点平衡因子 ∈ {-1, 0, 1}）
  - 插入后必须触发至少一次旋转
  - 旋转后树必须满足 AVL 性质
  - 四个选项必须互不相同
  - 干扰项必须对应明确的错误认知路径

adjustment_priority:
  1. 确保插入后触发旋转（否则降低 K3 推演需求）
  2. 确保旋转类型判断有区分度（避免仅 LL/RR 型过于简单）
  3. 确保干扰项对应真实认知错误

## terminology_and_expression_constraints
required_terms:
- 平衡因子（balance factor）
- 左旋（left rotation）
- 右旋（right rotation）
- LL型 / RR型 / LR型 / RL型
- 失衡结点（unbalanced node）
- 平衡二叉排序树 / 平衡二叉搜索树

required_qualifiers:
- 描述旋转时必须说明"对哪个结点执行旋转"
- 描述平衡因子时必须明确"左子树高度减右子树高度"或"右子树高度减左子树高度"的约定

avoid_phrases:
- "调整"（应使用"旋转"）
- "不平衡"（应使用"失衡"）
- "旋转一下"（应明确旋转类型和方向）

standard_rewrites:
  - bad: "对结点 A 进行调整" → good: "对结点 A 执行左旋/右旋操作"
  - bad: "树不平衡了" → good: "结点 X 的平衡因子绝对值超过 1，成为失衡结点"
  - bad: "做一次 LR 旋转" → good: "先对结点 Y 执行右旋，再对结点 X 执行左旋"

## audit_focus
final_review_must_check:
- 初始 AVL 树结构是否合法（所有结点平衡因子 ∈ {-1, 0, 1}）
- 插入操作是否触发至少一次旋转
- 旋转类型判断是否正确（LL/RR/LR/RL）
- 旋转后树结构是否满足 AVL 性质
- 四个选项是否互不相同且干扰项对应明确错误路径
- 设问是否清晰无歧义

solve_output_should_contain:
- 初始 AVL 树的结构描述（关键字与平衡因子）
- 插入结点的定位过程
- 平衡因子逐层更新过程
- 失衡结点定位与旋转类型判断依据
- 旋转操作执行过程（树结构变化）
- 旋转后各结点平衡因子重新计算结果
- 最终 AVL 树结构验证

fail_if_missing:
- 未展示平衡因子更新过程
- 未说明旋转类型判断依据
- 未验证旋转后 AVL 性质
- 干扰项无法对应到明确错误认知路径
- 初始树不合法或插入后未触发旋转
