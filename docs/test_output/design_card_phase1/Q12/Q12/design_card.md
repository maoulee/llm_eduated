## status

draft

## blueprint_contract

- slot_id: Q12
- question_type: 选择题
- score: 2
- target_subject: 计算机系统概述
- target_family: 组成原理-1 > 计算机系统概述 > 计算机性能指标 > CPU性能指标
- primary_target_name: CPU执行时间公式
- examination_mode: 计算型——公式应用与单位换算
- k_target: K1-K2平衡型
- difficulty_level: 3
- should_be: 需要准确记忆CPU执行时间公式，并完成常规参数代入与单位换算
- should_not_be: （蓝图未明确列出）
- hard_constraints: 难度3，K1-K2平衡型，2分选择题

## route

- question_form: 选择题
- question_type: computational
- requires_parameter_verification: true
- requires_solver: true
- requires_code: false

## core_knowledge_intent

- must_test:
  1. CPU执行时间核心公式 T_CPU = IC × CPI × T_clk = IC × CPI / f 的准确记忆与正确代入
  2. 频率单位（GHz/MHz）与时间单位（s/ms/μs/ns）之间的数量级换算关系
  3. 公式中各变量（指令数IC、CPI、主频f、时钟周期T_clk）的物理含义与相互关系
- must_not_shift_to:
  1. 不应偏向性能提升比例计算（如Amdahl定律、速度比推导）
  2. 不应偏向多级指标综合优化（如同时改变IC和CPI的复合优化场景）
- coverage_success_criteria:
  1. 考生能正确写出或识别CPU执行时间公式并完成一次完整代入计算
  2. 考生能在计算过程中正确处理至少一次单位换算（如GHz→Hz或s→ns）

## expected_reasoning_actions

1. 识别题干中给出的已知参数（如主频、CPI、指令数等），确定待求量
2. 根据已知参数与待求量，选择正确的CPU执行时间公式形式（T_CPU = IC × CPI / f 或其变形）
3. 检查各参数的单位是否统一，必要时进行单位换算（如GHz换算为Hz，或秒换算为纳秒）
4. 将参数代入公式完成数值计算，得出CPU执行时间结果
5. 将计算结果与四个选项对比，选出匹配项

## question_structure_plan

- stem_style: 题干给出一个CPU场景，提供若干性能指标参数（如主频、CPI、指令数中的部分已知量），要求计算某一未知量（如执行时间）
- option_architecture:
  - correct: 正确代入公式并完成单位换算后的准确数值
  - distractor_1: 单位换算错误（如GHz未换算为Hz，导致结果差10^9倍或数量级错误）
  - distractor_2: 公式记反或逻辑倒置（如用 f / (IC × CPI) 代替 IC × CPI / f）
  - distractor_3: 变量遗漏或参数误用（如漏乘CPI，或混淆时钟周期与主频）
- asking_method: 直接设问，要求选出计算结果（如"该程序的CPU执行时间为多少？"）

## parameter_plan

- parameter_slots:
  - IC（指令数）: 角色=已知参数或待求量, 候选范围=10^6~10^9量级, used_by=公式代入
  - CPI（每条指令平均时钟周期数）: 角色=已知参数, 候选范围=1~5之间的整数或简单小数, used_by=公式代入
  - f（主频）: 角色=已知参数, 候选范围=1~4 GHz, used_by=公式代入
  - T_clk（时钟周期）: 角色=可由主频推导或作为已知参数, 候选范围=0.25~1 ns, used_by=公式代入或验证
  - T_CPU（CPU执行时间）: 角色=待求量, 候选范围=ms~s量级, used_by=最终答案
- validation_targets:
  1. 正确答案必须通过 T_CPU = IC × CPI / f 精确计算得出
  2. 三个干扰项必须分别对应：单位换算错误、公式倒置、变量遗漏 三种典型错误路径
  3. 所有参数代入后计算结果应为合理数值，不宜出现极端小数或超大整数
- adjustment_priority:
  1. 优先调整IC和f使计算结果落在合理范围（ms~s）
  2. CPI取整数或简单小数以保证计算友好
  3. 单位换算路径应清晰，避免多级嵌套换算

## terminology_and_expression_constraints

- required_terms:
  - CPU执行时间（或程序执行时间）
  - 主频（或时钟频率）
  - CPI（或每条指令的平均时钟周期数）
  - 指令数（或程序指令条数）
  - 时钟周期
- required_qualifiers:
  - 频率单位必须明确标注 GHz/MHz/Hz
  - 时间单位必须明确标注 s/ms/μs/ns
  - 若涉及"平均"概念，需明确是"每条指令的平均时钟周期数"
- avoid_phrases:
  - 避免使用"速度"代替"频率"（速度易与执行速度混淆）
  - 避免使用"周期"单独出现而不加"时钟"限定（可能与指令周期混淆）
  - 避免使用"运算时间"（应为"执行时间"）
- standard_rewrites:
  - bad: "CPU速度为2GHz" → good: "CPU主频为2GHz"
  - bad: "周期为0.5ns" → good: "时钟周期为0.5ns"
  - bad: "运算时间为多少" → good: "CPU执行时间为多少"

## audit_focus

- final_review_must_check:
  1. 题干中给出的参数是否足以唯一确定待求量（不缺少必要参数，不冗余矛盾）
  2. 正确答案是否通过 T_CPU = IC × CPI / f 精确计算得出
  3. 三个干扰项是否分别对应三种不同典型错误（单位换算、公式倒置、变量遗漏），且互不重复
  4. 所有数值单位是否标注清晰，无歧义
  5. 计算过程是否符合难度3标准（常规代入+单位换算，非极端复杂计算）
- solve_output_should_contain:
  1. 明确写出的CPU执行时间公式
  2. 参数单位换算过程（如GHz→Hz）
  3. 代入公式的完整计算步骤
  4. 最终数值结果及单位
  5. 与正确选项的匹配说明
- fail_if_missing:
  1. 缺少公式引用或公式错误
  2. 缺少单位换算步骤
  3. 计算结果与任一选项不匹配
  4. 干扰项无法追溯到明确的错误路径
