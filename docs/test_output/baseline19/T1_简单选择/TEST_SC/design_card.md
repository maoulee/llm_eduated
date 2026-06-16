## status
draft

## blueprint_contract
slot_id: [待分配]
question_type: single_choice
score: 2
target_subject: 数据结构
target_family: DS-5 > 树与二叉树
primary_target_name: 二叉树带权路径长度
examination_mode: 给定二叉树结构+叶子权值，计算WPL
k_target: K1=2,K2=3,K3=3,K4=2,K5=1
difficulty_level: 3
should_be:
- 仅叶子节点有权值，非叶子节点无权值
- 路径长度定义为从根到叶子经过的边数
- WPL计算结果在30-100之间
- 树结构合法且清晰可读
should_not_be:
- 不涉及哈夫曼树构造
- 不涉及非叶子节点的权值计算
- 不涉及综合应用场景
hard_constraints:
- 节点总数: 8-15个
- 叶子节点数: 4-6个
- 树高度: 3-4层
- 叶子节点权值: 1-15之间的整数，不完全相同
- WPL结果: 30-100之间的整数

## route
question_form: single_choice
question_type: computational
requires_parameter_verification: true
requires_solver: true
requires_code: false

## core_knowledge_intent
must_test:
- WPL定义：所有叶子节点的权值乘以其路径长度之和
- 路径长度的计算：从根到叶子经过的边数
- 仅叶子节点参与WPL计算
must_not_shift_to:
- 哈夫曼树构造
- 非叶子节点的权值计算
coverage_success_criteria:
- 能正确识别所有叶子节点及其权值
- 能正确计算每个叶子节点的路径长度并应用WPL公式求和

## expected_reasoning_actions
- 识别二叉树中的所有叶子节点
- 确定每个叶子节点的权值
- 计算从根到每个叶子节点的路径长度（边数）
- 将每个叶子节点的权值与其路径长度相乘
- 将所有乘积求和得到WPL

## question_structure_plan
stem_style: 给定二叉树结构图（或文字描述）及各叶子节点的权值，直接询问WPL的值
option_architecture:
- correct: 正确WPL值
- distractor_1: 路径长度从1开始计数（而非从0）导致的错误值
- distractor_2: 包含非叶子节点计算导致的错误值
- distractor_3: 漏算某个叶子节点导致的错误值
asking_method: 直接问"该二叉树的带权路径长度WPL为多少"

## parameter_plan
parameter_slots:
- tree_structure: 二叉树结构，节点总数8-15，叶子4-6个，树高3-4层
- leaf_weights: 叶子节点权值，1-15之间的整数，不完全相同
- wpl_result: WPL计算结果，30-100之间的整数
validation_targets:
- 树结构合法性验证
- 仅叶子节点有权值
- WPL计算结果在30-100范围内
- 干扰项与正确答案的差异符合预期错误模式
adjustment_priority:
- 确保WPL结果在30-100范围内
- 确保干扰项与正确答案有合理差异
- 确保树结构清晰可读

## terminology_and_expression_constraints
required_terms:
- 带权路径长度（WPL）
- 叶子节点
- 路径长度
- 根节点
required_qualifiers:
- 路径长度定义为从根到该节点所经过的边数
- 仅叶子节点有权值
avoid_phrases:
- "层数"（易与路径长度混淆）
- "深度"（需明确是从根开始的边数）
standard_rewrites:
- bad: "第3层的节点" → good: "路径长度为2的节点"
- bad: "节点的深度" → good: "从根到该节点的路径长度"

## audit_focus
final_review_must_check:
- WPL计算结果是否正确
- 干扰项是否对应预期的错误认知路径
- 树结构描述是否清晰无歧义
- 是否明确说明仅叶子节点有权值
solve_output_should_contain:
- 所有叶子节点的识别
- 每个叶子节点的路径长度
- WPL的逐步计算过程
- 最终WPL值
fail_if_missing:
- WPL计算结果不在30-100范围内
- 干扰项与正确答案无合理差异
- 树结构描述存在歧义
