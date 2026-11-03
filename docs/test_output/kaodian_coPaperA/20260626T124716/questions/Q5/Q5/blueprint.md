## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: 计算机组成原理 > CO-1 计算机系统概述 > 计算机性能指标
- primary_target_name: CPU性能指标（MIPS/CPI）
- question_type: comprehensive
- examination_mode: 计算型——公式应用与多步计算

### 难度目标
- k_target: K1=2,K2=4,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 计算题，需多步公式代入（加权CPI→MIPS→执行时间比较），涉及非2幂次运算和单位换算，K2主导

### 结构要求
- sub_question_count: 3
- sub_question_details:
  - 第1问(3分): 计算两台机器各自平均CPI，加权求和
  - 第2问(3分): 计算两台机器各自MIPS，依赖第1问结果
  - 第3问(4分): 比较两机器执行同一基准程序的性能，依赖第2问
- dependency: 串行（第1问→第2问→第3问）
- condition_count: 3-4

### 参数约束
- 机器A主频 f_A: 1-4 GHz，取值使两机器主频差异显著
- 机器B主频 f_B: 1-4 GHz，f_B ≠ f_A，|f_A - f_B| ≥ 1 GHz
- 指令类数 n: 3-5类
- 各指令类CPI: 1-6的整数，机器A与机器B在至少2类指令上的CPI不同
- 指令频率 {p_i}: n个正数，Σp_i = 1
- 基准程序指令总数 N: 友好量级整数（如10⁸）
- 一致性约束:
  - 加权平均CPI_A ≠ CPI_B
  - MIPS_A ≠ MIPS_B
  - 两机器执行时间不相等（确保第3问有明确结论）

### 参考经验摘要
- 历史模式: 原卷计算Q1——给定两机器主频和指令CPI表，计算各自MIPS并比较性能
- 难度锚点: K2=4主导，通过多步公式代入和MHz/GHz单位换算制造计算负荷
- 典型陷阱: 单位换算错误、加权平均误用算术平均、MIPS公式分子分母颠倒、指令频率未验证求和为1
