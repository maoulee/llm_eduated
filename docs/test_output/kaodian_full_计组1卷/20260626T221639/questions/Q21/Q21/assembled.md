## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: CO-1 > 计算机系统概述 > 计算机性能指标 > CPU性能指标
- primary_target_name: CPU性能指标(CPI/MIPS)
- question_type: subjective
- examination_mode: 计算型——CPI与执行时间

### 难度目标
- k_target: K1=2,K2=4,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 核心考察代公式计算，K2=4为最大挑战（非2幂次乘加+多级单位换算）；K1=2仅需基础公式记忆；K3=2两步串行路径唯一；K4/K5为低

### 结构要求
- sub_question_count: 2
- sub_question_types: [计算, 计算]
- score_allocation: 3分 + 3分
- dependency: 串行——第2问依赖第1问的平均CPI结果
- condition_count: 3（指令类型表格 + 程序指令总数 + 时钟频率）

### 子问题规格
- **第1问（3分）**：根据指令类型/CPI/比例表格，计算加权平均CPI
  - formula: CPI_avg = Σ(CPI_i × 占比_i)
  - k_target: K2=4
  - 易错点: 加权乘加中非2幂次运算导致小数结果
- **第2问（3分）**：利用平均CPI、指令总数、时钟频率计算程序执行时间
  - formula: T = (N × CPI_avg) / f
  - k_target: K2=4
  - 易错点: 单位换算（GHz→Hz，ns→μs/ms）

### 参数约束
- 指令类型数: 3-5种（建议4种）
- 各类型CPI: 1-12之间的整数，至少1种为非2幂次
- 各类型占比: 整数百分比，和为100%，至少1个占比为非2幂次
- 平均CPI结果: 必须为非整数（含小数）
- 程序指令总数: 10^4~10^6量级整数
- 时钟频率: 1~4 GHz，时钟周期建议为友好小数
- 执行时间结果: μs~ms范围，需至少一次单位换算

### 干扰策略（主观题不适用，但设计注意事项）
- 表格设计须使加权CPI为非整数，防止口算秒杀
- 单位换算须真实存在，否则K2降级

### 参考经验摘要
- 历史模式: 计算型CPI题，表格→加权CPI→执行时间两步串行
- 难度锚点: K2=4对应非2幂次+单位换算
- 典型陷阱: 单位换算错误、占比未归一、CPI与时钟周期混淆
