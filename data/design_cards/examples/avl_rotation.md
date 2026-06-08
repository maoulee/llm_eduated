# design_card

## status
draft

## blueprint_contract
- slot_id: Q42
- question_type: comprehensive
- score: 10
- target_subject: 数据结构
- target_family: 树与二叉树 > 平衡二叉树
- primary_target_name: AVL树插入与旋转调整
- examination_mode: 机制模拟与推演型 (Simulation & Derivation)
- k_target: K2-K4递进型
- difficulty_level: 4
- should_be:
  - 围绕 AVL 插入后的失衡判断与旋转调整设计
  - 子问题之间应体现"插入过程 → 旋转类型 → 调整后结构"的递进关系
  - 至少考察一次旋转类型判断
- should_not_be:
  - 不应退化为普通二叉搜索树插入题
  - 不应只考遍历序列
  - 不应要求开放式描述 AVL 的定义
- hard_constraints:
  - 综合题必须包含多个子问题
  - 题干不得包含编程代码
  - 不得在题目中写出答案

## route
- question_form: comprehensive
- question_type: computational
- requires_parameter_verification: true
- requires_solver: true
- requires_code: true

## core_knowledge_intent
- must_test:
  - AVL 插入后从插入结点向上寻找首个失衡结点
  - 根据插入路径判断 LL / LR / RR / RL 旋转类型
  - 执行旋转并得到调整后的局部或整体树结构
- must_not_shift_to:
  - 普通 BST 插入
  - 单纯二叉树遍历
  - 只背诵 AVL 平衡因子定义
- coverage_success_criteria:
  - 解题过程必须出现失衡结点判断
  - 解题过程必须出现旋转类型判断
  - 解题过程必须给出旋转后的树结构或关键父子关系

## expected_reasoning_actions
- action_1: 按二叉搜索树规则依次插入给定结点
- action_2: 每次插入后沿插入路径向上检查平衡因子
- action_3: 定位首个失衡结点
- action_4: 根据新结点相对失衡结点及其子结点的位置判断旋转类型
- action_5: 执行对应旋转并更新局部子树结构
- action_6: 在最终树上判断指定结点的高度、平衡因子或父子关系

## question_structure_plan
- shared_context: 给出一棵初始 AVL 树和一个插入序列
- sub_question_chain:
  - q1_role: 判断某次插入后首个失衡结点及旋转类型
  - q2_role: 给出完成全部插入后的 AVL 树结构
  - q3_role: 基于最终树判断某个结点的平衡因子或树高
- dependency_pattern:
  - q2 depends on q1 的旋转调整结果
  - q3 depends on q2 的最终树结构
- asking_method:
  - 使用"判断""写出""计算"作为设问动词
  - 避免开放式解释题

## parameter_plan
- parameter_slots:
  - name: initial_tree
    role: 初始 AVL 树结构
    candidate_range: 7 至 9 个结点，保持初始平衡
    used_by: q1, q2, q3
  - name: insertion_sequence
    role: 触发指定旋转并形成最终树
    candidate_range: 3 至 5 个插入值
    used_by: q1, q2
  - name: target_node
    role: 最终树性质判断对象
    candidate_range: 从最终树中选择非根内部结点或根结点
    used_by: q3
- validation_targets:
  - 初始树必须满足 BST 性质
  - 初始树必须满足 AVL 平衡性质
  - 插入序列中每个值不得与已有结点重复
  - 至少一次插入必须触发旋转
  - q1 指定的插入时刻必须能唯一判断旋转类型
  - 最终树必须仍满足 BST 与 AVL 性质
- adjustment_priority:
  - 优先调整 insertion_sequence
  - 其次调整 initial_tree 的局部结构
  - 不改变考察目标和子问题链

## terminology_and_expression_constraints
- required_terms:
  - 平衡因子
  - 首个失衡结点
  - LL / LR / RR / RL 型调整
  - 旋转
- required_qualifiers:
  - 明确插入按二叉搜索树规则进行
  - 明确空树高度或叶结点高度采用的约定；若不涉及具体高度可不声明
- avoid_phrases:
  - "旋转一下"
  - "调整平衡"但不说明旋转类型
  - "画出树"但不给出可判定的文本格式要求
- standard_rewrites:
  - bad: 判断是哪种不平衡
    good: 判断首个失衡结点及应采用的 AVL 旋转类型

## audit_focus
- final_review_must_check:
  - 题目是否确实考察 AVL 插入与旋转，而非普通 BST 插入
  - q1 是否能唯一确定旋转类型
  - q2 的最终树是否与 solver 输出一致
  - q3 是否基于最终树，而不是独立概念判断
- solve_output_should_contain:
  - 插入路径
  - 首个失衡结点
  - 旋转类型
  - 旋转后的局部树结构
  - 最终树结构
- fail_if_missing:
  - 缺少首个失衡结点判断
  - 缺少旋转类型判断
  - 最终树不满足 BST 或 AVL 性质
  - 子问题之间没有依赖关系
