## status
draft

## blueprint_contract
- slot_id: Q45
- question_type: comprehensive
- score: 蓝图未显式指定（综合应用题，建议 10–13 分）
- target_subject: 操作系统
- target_family: 进程与线程 > 死锁 > 死锁避免
- primary_target_name: 银行家算法
- examination_mode: 资源分配与安全性推演
- k_target: K3-K4平衡型
- difficulty_level: 4
- should_be:
  - 需多步推演资源状态变化以寻找安全序列
  - 需深入理解安全状态的隐含前提（安全状态与死锁状态的关系）
  - 需执行完整的银行家算法安全性检查流程（Need 计算 → 请求合法性检查 → 试探性分配 → 安全性算法）
  - 需计算 Need 矩阵（Need = Max − Allocation）
- should_not_be:
  - 不应仅考查概念记忆而不考查推演
  - 不应涉及死锁检测算法或资源分配图
  - 不应简化为一步即可判断的资源分配场景
- hard_constraints:
  - 知识点锁定为银行家算法，不可偏移到死锁预防/检测/避免的其他子方法
  - 考察模式为"资源分配与安全性推演"，必须包含安全序列的推演过程
  - 难度 4，K3-K4 平衡型：K3≥4 且 K4≥4 为主导区分维度
  - 必须考查安全状态的隐含前提（安全≠无死锁的反面）

## route
- question_form: comprehensive
- question_type: mixed
- requires_parameter_verification: true
- requires_solver: true
- requires_code: true

## core_knowledge_intent
- must_test:
  - 银行家算法的完整执行流程：Need 矩阵计算 → 请求合法性验证（Request ≤ Need 且 Request ≤ Available）→ 试探性分配 → 安全性算法判定
  - 安全状态的判定方法：能找到一个进程完成序列（安全序列）使所有进程都能获得所需资源并顺利完成，则系统处于安全状态
  - 安全状态与死锁的隐含关系：安全状态 → 一定无死锁；不安全状态 ↛ 一定死锁（仅有可能死锁）
- must_not_shift_to:
  - 死锁检测算法（基于资源分配图的死锁定理），与银行家算法的死锁避免是不同机制
  - 死锁预防策略（破坏四个必要条件之一）或鸵鸟策略
- coverage_success_criteria:
  - 学生能正确计算 Need 矩阵的所有条目
  - 学生能完整执行安全性算法，正确更新 Available 向量并给出一个有效的安全序列
  - 学生能正确阐述安全状态与死锁状态的关系，不混淆"不安全"与"死锁"

## design_rationale
本题以银行家算法为核心，设计为三段递进式综合题，旨在区分"能完整执行安全性算法并理解安全状态本质"的学生与"仅记住步骤但无法正确推演或缺乏深层理解"的学生。选择 K3=4（多步动态状态推演）和 K4=4（安全状态隐含前提）作为主导维度，是因为银行家算法的教学价值恰恰在于其推演过程的复杂性和安全状态概念的非直觉性。安全性算法要求学生在每一步选择可满足的进程后，回收其资源更新 Available 向量并继续搜索，涉及 5 个以上进程的状态追踪，中间任何一步出错都会导致后续全部偏离——这是 K3=4 的典型特征。同时，"安全状态一定无死锁但不安全状态不一定死锁"这一隐含前提是学生最容易误解的知识点，需要通过具体场景而非纯概念辨析来检验——这是 K4=4 的典型特征。三段式结构（Need 计算 → 请求判定 → 安全序列与概念理解）确保了从基础到高阶的认知梯度：SQ1 作为入题门槛（K1/K2），SQ2 作为核心推演区分器（K3），SQ3 同时检验推演能力（K3）和深层概念理解（K4）。难度 4 对应"推演步数适中但需维护动态状态变量，且存在需要深入理解的隐含前提"，适合作为综合应用题的中高难度题目。题面参数应设计为使安全序列非平凡（非简单的进程编号顺序），且资源请求处于"通过合法性检查但需完整安全性算法才能判定"的边界状态，迫使考生走完全流程而非凭直觉跳答。

## expected_reasoning_actions
- 根据 Max 矩阵和 Allocation 矩阵，逐条目计算 Need 矩阵（Need[i][j] = Max[i][j] − Allocation[i][j]）
- 验证资源请求的两步合法性：先检查 Request ≤ Need，再检查 Request ≤ Available
- 执行试探性分配：将 Request 从 Available 中扣除、加入对应进程的 Allocation、从 Need 中扣除
- 执行安全性算法：设工作向量 Work = Available，逐轮扫描进程，找到 Need ≤ Work 的进程，回收其 Allocation 加入 Work，标记完成，直至所有进程完成或无法继续
- 根据 safety check 结果判定是否批准请求（安全则批准并恢复试探性分配为正式分配，不安全则回滚）
- 给出一个完整的安全序列（进程完成顺序）
- 阐述安全状态与死锁状态的关系：安全状态一定不会发生死锁，不安全状态不一定会发生死锁

## question_structure_plan
- question_form: comprehensive
- shared_context: 某系统有 5 个进程（P0–P4）和 3 类资源（A、B、C），给定 Max 矩阵、Allocation 矩阵和 Available 向量；某进程提出资源请求
- sub_question_chain:
  - SQ1（基础，~3 分）：根据 Max 和 Allocation 矩阵，写出 Need 矩阵。—— 考查 K1/K2，作为入题门槛，无前置依赖。
  - SQ2（核心，~5 分）：某进程 P_x 提出一组资源请求 Request，用银行家算法判断是否可以分配，并说明判定依据。—— 考查 K3（多步安全性推演）+ K4（理解何时批准/拒绝），依赖 SQ1 的 Need 矩阵。
  - SQ3（高阶，~4 分）：若分配后系统处于安全状态，给出一个安全序列；并简述安全状态与死锁状态的关系。若处于不安全状态，说明原因并同样简述安全状态与死锁的关系。—— 考查 K3（安全序列搜索）+ K4（隐含前提理解），依赖 SQ2 的判定结果。
- dependency_pattern: 线性链 SQ1 → SQ2 → SQ3；SQ2 必须使用 SQ1 的 Need 矩阵结果，SQ3 必须使用 SQ2 的分配判定结果
- interference_design（综合题常见错误路径，非选择题干扰项）:
  - 中间值陷阱：安全性算法中途找到部分进程可满足后停止，报告不完整序列为安全序列
  - 条件遗漏：只检查 Request ≤ Available 而忘记先检查 Request ≤ Need，或反之
  - 偏移错误：试探性分配时 Available 更新方向错误（加而非减，或减而非加），或 Need 未同步更新
  - 概念混淆：将"不安全状态"等同于"死锁状态"

## parameter_plan
- parameter_slots:
  - name: num_processes | role: 系统中进程数量 | candidate_range: 4–5（建议 5） | used_by: SQ1/SQ2/SQ3
  - name: num_resource_types | role: 资源类别数 | candidate_range: 3（A/B/C，标准值） | used_by: SQ1/SQ2/SQ3
  - name: total_resources | role: 各类资源的总量 | candidate_range: 每类 10–20 的整数 | used_by: 验证 Available 一致性
  - name: max_matrix | role: 各进程最大需求矩阵 | candidate_range: 每条目 0–10 的整数 | used_by: SQ1
  - name: allocation_matrix | role: 各进程已分配矩阵 | candidate_range: 每条目 0–Max 对应条目 | used_by: SQ1
  - name: available_vector | role: 当前可用资源向量 | candidate_range: total − Σ(allocation)，每分量 ≥ 0 | used_by: SQ2
  - name: requesting_process | role: 提出请求的进程编号 | candidate_range: P0–P4 之一 | used_by: SQ2
  - name: request_vector | role: 资源请求向量 | candidate_range: 每分量 ≤ Need[ requesting_process ] 对应分量，且 ≤ Available 对应分量 | used_by: SQ2
- validation_targets:
  - Need 矩阵所有条目 ≥ 0（Max ≥ Allocation 对所有 i,j）
  - Available = Total − Σ(Allocation 按列求和)，三者数值一致
  - 初始状态（分配请求前）必须是安全状态，至少存在一个安全序列
  - 试探性分配后（批准请求后）仍为安全状态，以支持 SQ3 要求给出安全序列
  - 试探性分配后的安全序列必须非平凡——不是简单的 P0→P1→P2→P3→P4 编号顺序，至少有一个进程需"等待"到后续轮次才能满足
  - 所有数值为小整数（0–10），避免计算复杂度掩盖对机制的理解
  - 安全性算法执行步数 5–7 步（K3=4 适配）
- adjustment_priority:
  1. request_vector：控制安全性检查的难度边界，是调节 K3 难度的首要旋钮
  2. available_vector：控制资源紧张程度，影响安全序列的非平凡性
  3. allocation_matrix：控制 Need 矩阵结构，影响安全序列的搜索路径
  4. max_matrix：控制整体资源需求格局，影响初始安全状态的验证

## terminology_and_expression_constraints
- required_terms:
  - 安全序列（safety sequence）
  - 安全状态（safe state）/ 不安全状态（unsafe state）
  - Need 矩阵 / 最大需求矩阵（Max）/ 已分配矩阵（Allocation）/ 可用资源向量（Available）
  - 银行家算法（Banker's Algorithm）
  - 安全性算法 / 安全性检查（safety algorithm）
- required_qualifiers:
  - "试探性分配"——必须强调分配是临时假设的，待安全性检查通过后才正式确认
  - "存在一个安全序列"——安全状态的判定标准是"存在性"而非"唯一性"
  - "工作向量 Work"——安全性算法中使用的临时变量，初始等于 Available
- avoid_phrases:
  - "不安全就是死锁"——错误等同，应区分不安全状态与死锁状态
  - "可以分配因为还有资源"——安全判定依据是安全序列的存在性，不是简单的资源剩余
  - "一定不会死锁"用于描述不安全状态——不安全状态只是"可能"死锁
- standard_rewrites:
  - bad: "系统还有资源所以是安全的" → good: "存在一个安全序列使所有进程都能顺利完成，因此系统处于安全状态"
  - bad: "不安全状态就是死锁" → good: "不安全状态可能发展为死锁，但并非一定已经死锁"
  - bad: "检查 Request 就行" → good: "先检查 Request ≤ Need，再检查 Request ≤ Available，最后执行安全性算法"

## audit_focus
- final_review_must_check:
  - Need 矩阵计算是否正确（所有 5×3=15 个条目）
  - 安全性算法的执行是否完整——是否逐轮更新 Work 向量并标记完成进程
  - 给出的安全序列是否有效——按序列顺序验证每步 Need ≤ Work 成立
  - 是否正确区分"安全状态"与"不安全状态"的判定
  - 是否正确阐述安全状态与死锁状态的关系（安全→无死锁，不安全↛死锁）
  - 参数是否满足所有 validation_targets（初始安全、试探性分配后安全、序列非平凡）
- solve_output_should_contain:
  - 完整的 Need 矩阵（5 行 × 3 列）
  - 请求合法性检查的两步结果（Request ≤ Need 通过/失败 + Request ≤ Available 通过/失败）
  - 安全性算法的逐步执行过程：每一轮选择的进程、更新后的 Work 向量、完成标记
  - 至少一个有效的安全序列（进程编号顺序）
  - 安全状态与死锁关系的文字说明
- fail_if_missing:
  - Need 矩阵有任何计算错误
  - 安全性算法中途停止或 Work 向量更新错误
  - 安全序列无法通过逐步验证（某步 Need > Work）
  - 将"不安全状态"等同于"死锁状态"
  - 缺少 Request ≤ Need 或 Request ≤ Available 中的任一检查
  - 题目参数不满足 validation_targets（初始状态不安全、或试探性分配后不安全导致 SQ3 无法出题）
