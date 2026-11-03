## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: CO-1 计算机系统概述 > 计算机性能指标
- primary_target_name: CPU性能指标（MIPS/CPI）
- question_type: comprehensive
- examination_mode: 计算型——公式应用与多步计算

### 难度目标
- k_target: K1=2,K2=4,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 计算题，需多步公式代入（加权CPI→MIPS），K2主导；多级单位换算和加权计算使单步代入繁杂度达4，其余维度为低

### 结构要求
- sub_question_count: 3
- sub_question_details:
  - 第1问（4分）: 计算机器A和B的加权平均CPI
  - 第2问（3分）: 计算机器A和B的MIPS
  - 第3问（3分）: 比较两台机器性能，给出依据
- dependency: serial（第1问→第2问→第3问）
- distractor_strategy: 不适用（计算题非选择题）

### 参数约束
- 机器A时钟频率: 200-800 MHz，整数，与机器B不同
- 机器B时钟频率: 200-800 MHz，整数，与机器A不同
- 指令类别数: 3-4类，两台机器类别集合相同
- 各类指令CPI（机器A）: 1-8，正整数，每类不同
- 各类指令CPI（机器B）: 1-8，正整数，与机器A不完全相同
- 指令混合比例: 各类10%-50%，之和=100%，两台机器共用
- 程序总指令数（可选）: 10⁶-10⁹条，10的幂次
- MIPS差异约束: 两台机器MIPS差异在10%-30%之间

### 参考经验摘要
- 历史模式: 408经典MIPS/CPI计算题，大题基础计算位
- 难度锚点: K2主导（K2=4），K1=2/K3=2/K4=2/K5=1
- 典型陷阱:
  1. 百分比未转小数代入加权CPI
  2. 时钟频率单位未统一
  3. 误认高MIPS=高性能
  4. 加权CPI遗漏指令类别
