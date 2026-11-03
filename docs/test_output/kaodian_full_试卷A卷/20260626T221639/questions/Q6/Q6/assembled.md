## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: CO-2 数据的表示和运算 > 定点数的运算
- primary_target_name: 补码加减运算与溢出判断
- question_type: comprehensive
- examination_mode: 计算型——补码运算与溢出判断

### 难度目标
- k_target: K1=2,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 计算题，需多步串行推演（求补码→双符号位加法→判溢出），K3主导，K2辅助（单步计算含非2幂次），K1/K4/K5偏低

### 结构要求
- sub_question_count: 3
- sub_question_types: [计算, 计算, 分析]
- sub_question_scores: [3, 4, 3]
- sub_question_dependency: 串行（第2问依赖第1问，第3问依赖第2问）
- condition_count: 2-3
- distractor_strategy: 不适用（计算题，非选择题）

### 参数约束
- x: 定点小数，绝对值 ∈ [0.5, 0.99]，可正可负
- y: 定点小数，绝对值 ∈ [0.5, 0.99]，可正可负
- x_y_relationship: 至少一个为负数（确保考察补码转换）；若考察溢出则x与y同号且|x+y|超出可表示范围，若考察不溢出则x与y异号或同号但和不超范围
- n: 数值位数 = 4 或 5
- total_bits: n + 2（含双符号位）
- precision: x和y的二进制表示在n位内精确，无截断误差
- freedom: Question Agent 自由选择具体数值、正负组合、是否溢出、n取值

### 参考经验摘要
- 历史模式: 求补码→双符号位加法→判溢出，固定三步流程
- 难度锚点: K3=3主导，整体难度3
- 典型陷阱: 忽略双符号位直接用单符号位运算；负数补码转换忘末位加1
