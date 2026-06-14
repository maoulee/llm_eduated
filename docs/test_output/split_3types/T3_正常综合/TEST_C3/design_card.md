## status
draft

## blueprint_contract
- slot_id: Q41
- question_type: comprehensive
- score: 8
- target_subject: 数据结构
- target_family: 树与二叉树 > 树与二叉树的应用 > 平衡二叉树 AVL
- primary_target_name: 平衡二叉树 AVL 的插入与旋转
- examination_mode: 结构操作与状态维护模拟
- k_target: K3-K4平衡型
- difficulty_level: 4
- should_be:
  - 需多步串行推演AVL树的形态变化（插入步数≥6）
  - 需精准辨析四种旋转类型（LL/RR/LR/RL）的触发条件
  - 至少触发一次旋转调整，要求考生完整模拟插入-检测-调整过程
  - 考察平衡因子的动态计算与更新
- should_not_be:
  - 不考AVL树的删除操作及删除后的平衡调整
  - 不涉及红黑树、B树、B+树等其他自平衡树
  - 不需要编程实现，纯手工推演
  - 不偏移到AVL查找效率/ASL分析（除非作为副产品附带）
- hard_constraints:
  - 插入序列必须唯一确定每一步的树形态，无多种合法解释
  - 必须至少触发一次旋转，且旋转类型无歧义
  - 最终树必须是合法AVL树（所有节点|平衡因子|≤1）
  - 平衡因子定义需在题干中明确（左子树高度-右子树高度）

## route
- question_form: comprehensive
- question_type: mixed
- requires_parameter_verification: yes
- requires_solver: yes
- requires_code: yes

## core_knowledge_intent
- must_test:
  1. AVL树插入后的平衡因子计算与失衡检测——定位最小不平衡子树
  2. 四种旋转类型（LL/RR/LR/RL）的触发条件辨识与正确执行
  3. 多步串行插入过程中树形态的动态追踪与状态维护
- must_not_shift_to:
  1. AVL树的删除操作及删除后的平衡维护
  2. 红黑树、B树等其他自平衡树的性质与操作
- coverage_success_criteria:
  1. 考生能完整模拟6-8个关键码的AVL插入过程，正确计算每步的平衡因子
  2. 考生能准确识别失衡类型并描述旋转后的正确树结构

## expected_reasoning_actions
- 依次插入关键码，为每个新节点计算平衡因子并沿祖先链向上更新
- 检测第一个平衡因子绝对值超过1的节点，确定其为最小不平衡子树的根
- 根据失衡节点及其左/右子节点的高度差方向，判定旋转类型（LL/RR/LR/RL）
- 执行对应旋转操作，正确重新连接旋转涉及的子树
- 继续插入剩余关键码，重复失衡检测与调整过程
- 在最终AVL树中定位目标节点，读取其平衡因子或子节点关系

## question_structure_plan
- shared_context: 给定一组互不相同的关键码依次插入初始为空的AVL树，模拟完整的插入-调整过程。题干明确平衡因子定义（左子树高度-右子树高度）。
- sub_question_chain:
  - 子问题1（基础模拟，约2分）：插入前若干个关键码后（旋转发生前），描述当前树的形态——考察插入操作与平衡因子计算
  - 子问题2（旋转辨识，约3分）：在指定的插入步骤中，指出失衡节点、旋转类型，并描述旋转后的树结构——考察旋转类型辨识与执行
  - 子问题3（完整推演，约3分）：全部插入完成后，确定最终AVL树中某指定节点的平衡因子或子节点——考察完整推演能力
- dependency_pattern: 串行依赖——子问题2的旋转判断基于子问题1的树形态，子问题3的最终结构依赖完整的插入-调整推演
- student_error_patterns:
  1. 旋转类型混淆：将LR型误判为LL型或RL型（概念混淆干扰）
  2. 平衡因子符号定义不一致：使用右-左而非左-右，导致旋转方向判断反转（条件遗漏干扰）
  3. 旋转后子树连接错误：双旋转中遗漏中间子树的重新挂接（中间值/过程错误干扰）

## parameter_plan
- parameter_slots:
  - name: insertion_sequence
    role: 驱动整个AVL插入模拟的关键码序列
    candidate_range: 6-8个互不相同的正整数（建议取值范围1-20）
    used_by: 所有子问题
  - name: rotation_trigger_step
    role: 触发旋转的具体插入步骤序号
    candidate_range: 第4-6个插入
    used_by: 子问题2
  - name: rotation_type
    role: 本题需要触发的旋转类型
    candidate_range: LL/RR/LR/RL 四选一（建议优先选择LR或RL双旋，增加K4辨识难度）
    used_by: 子问题2
  - name: query_node
    role: 子问题3中需要查询属性的节点关键码
    candidate_range: 最终AVL树中的任意非叶节点
    used_by: 子问题3
- validation_targets:
  - 插入序列必须唯一确定每一步的树形态
  - 在rotation_trigger_step必须触发且仅触发指定rotation_type类型的旋转
  - 旋转类型判定必须无歧义
  - 最终树必须是合法AVL树（所有节点|平衡因子|≤1）
  - query_node在最终树中的位置和属性必须明确无歧义
- adjustment_priority:
  1. insertion_sequence（决定整体推演路径和旋转触发）
  2. rotation_type（决定子问题2的考察焦点和K4难度）
  3. query_node（影响子问题3的难度微调）

## terminology_and_expression_constraints
- required_terms:
  - 平衡因子
  - 最小不平衡子树
  - LL型/RR型/LR型/RL型旋转（或左单旋/右单旋/先左后右双旋/先右后左双旋）
  - 失衡
- required_qualifiers:
  - "依次插入"（强调插入顺序的重要性）
  - "初始为空"（明确初始状态）
  - "互不相同"（强调关键码唯一性）
  - "平衡因子=左子树高度-右子树高度"（必须在题干中明确定义）
- avoid_phrases:
  - "平衡旋转"（模糊，应明确为具体旋转类型）
  - "调整"单独使用无修饰（应说明具体调整方式）
  - "AVL树"未首次定义就使用（首次出现应给出全称"平衡二叉树（AVL树）"）
- standard_rewrites:
  - bad: "对树进行调整" → good: "对最小不平衡子树执行LR型旋转"
  - bad: "树不平衡了" → good: "节点X的平衡因子为2，以X为根的子树失衡"
  - bad: "旋转一下" → good: "执行RR型（右单）旋转"

## audit_focus
- final_review_must_check:
  - 插入序列是否唯一确定每步树形态（不存在多种合法的AVL结构解释）
  - 旋转触发点是否确实产生指定类型的旋转（必须由代码验证，不可目测）
  - 子问题链是否构成合理的难度递进（基础模拟→旋转辨识→完整推演）
  - K3维度是否达到4级（插入步数≥6，需维护动态状态）
  - K4维度是否达到3-4级（旋转类型辨识需理解失衡本质，非字面匹配）
  - 平衡因子定义是否在题干中明确给出
  - 评分标准是否覆盖student_error_patterns中的常见错误
- solve_output_should_contain:
  - 每个插入步骤后的完整树结构（节点值、父子关系、各节点平衡因子）
  - 旋转类型判定的完整推理链（失衡节点→子节点方向→孙节点方向→旋转类型）
  - 旋转前后树结构的对比
  - 最终AVL树的完整结构图
  - 各子问题的明确答案（数值或结构描述）
- fail_if_missing:
  - 插入序列无法唯一确定树形态
  - 旋转触发点未产生预期类型的旋转
  - 子问题之间无逻辑依赖（各自独立，未构成推演链）
  - 最终树不是合法AVL树
  - 未涉及旋转类型辨识（仅考察插入而无调整操作）
  - 平衡因子定义缺失或前后不一致
