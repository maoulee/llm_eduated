## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: 数据表示与运算 > IEEE754
- primary_target_name: IEEE754 浮点加减运算（对阶/规格化/舍入）
- question_type: comprehensive
- examination_mode: 计算题——给定两个 IEEE754 单精度数相加，写出对阶、尾数求和、规格化、舍入过程与结果

### 难度目标
- k_target: K1=3,K2=3,K3=4,K4=3,K5=1
- difficulty_level: 4
- difficulty_rationale: K3=4 为核心难度来源——需 >5 步串行推演（拆机器数→对阶→求和→判规格化方向→执行规格化→舍入→还原机器数），维持动态中间状态；阶码差≥2保证对阶非平凡，舍入非平凡保证四步全考

### 结构要求
- sub_question_count: 4
- sub_question_details:
  - (1) 对阶（2分）：比较阶码，小阶尾数右移对齐，写出对阶后两尾数
  - (2) 尾数求和（2分）：考虑符号后尾数加减，写出和的符号与尾数
  - (3) 规格化（3分）：判断左规/右规，执行规格化，写出规格化后尾数与阶码
  - (4) 舍入与最终结果（3分）：round-to-nearest-even 舍入，输出最终IEEE754机器数（十六进制）
- dependency: 严格串行 (1)→(2)→(3)→(4)
- condition_count: 2（两个十六进制IEEE754单精度机器数）
- distractor_strategy: 不适用（计算题无选项）

### 参数约束
- param_A: IEEE754单精度机器数（十六进制），阶码 E_A ∈ [1, 254]，非0/非规格化/非Inf/非NaN
- param_B: IEEE754单精度机器数（十六进制），阶码 E_B ∈ [1, 254]，非0/非规格化/非Inf/非NaN
- constraint_1: |E_A - E_B| ∈ [2, 5]，保证对阶有实质移位
- constraint_2: 尾数求和后需要规格化操作（非已规格化状态）
- constraint_3: 对阶右移后被移出的低位不全为0，舍入步骤非平凡
- constraint_4: 最终结果阶码 ∈ [2, 253]，不触发上溢/下溢
- constraint_5: 求和结果 ≠ 0
- constraint_6: 两数可同号或异号
- consistency_check: 参数需通过 gen.py 验证全部约束满足
- design_freedom: Question Agent 自由选择具体机器数值，满足以上约束即可

### 参考经验摘要
- 历史模式: IEEE754 浮点加法全流程四步计算（对阶→求和→规格化→舍入），408高频综合题型
- 难度锚点: K3=4 对应多步串行推演，阶码差≥2 + 需舍入时达到标准综合题难度
- 典型陷阱:
  1. 对阶方向错误（大阶向小阶对齐）
  2. 规格化方向判断错误
  3. 舍入后尾数溢出需二次右规——易遗漏
  4. 忽略隐含最高位1导致尾数对齐错误
  5. 异号相加时符号处理错误
