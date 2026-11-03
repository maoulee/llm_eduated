## 出题契约

### 基本信息
- target_subject: 组成原理
- target_family: 组成原理 > CO-3 存储系统 > 主存储器和CPU的连接 > 主存容量扩展
- primary_target_name: 存储器扩展（字位同时扩展）
- question_type: comprehensive
- examination_mode: 计算型——存储器扩展芯片数量

### 难度目标
- k_target: K1=3,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 2
- difficulty_rationale: 需理解字位同时扩展原理并做芯片分组计算，核心在于正确分离字扩展和位扩展两个维度；计算量为标准水平，无跨域联动，属基础计算应用题

### 结构要求
- sub_question_count: 2
- sub_question_details:
  - 第1问: 计算地址线根数和数据线根数，2分，独立计算
  - 第2问: 计算字扩展倍数、位扩展倍数和总芯片数，4分，核心考查
- sub_question_relationship: 串行（第2问依赖第1问对目标容量/字长的理解）
- condition_count: 2（目标存储器容量+存储字长；芯片规格）

### 参数约束
- 目标存储器总容量 C_target: 16KB ~ 256KB，2 的幂次 KB
- 目标存储字长 W_target: 8 位或 16 位
- 芯片地址单元数 N_chip: 1K ~ 16K，2 的幂次
- 芯片位宽 W_chip: 1、2、4、8 位之一
- 一致性约束:
  - 字扩展倍数 = C_target / N_chip ≥ 2
  - 位扩展倍数 = W_target / W_chip ≥ 2
  - 总芯片数 = 字扩展倍数 × 位扩展倍数
  - W_target 必须是 W_chip 的整数倍
  - C_target / N_chip 必须整除
- 数值友好性: 所有参数为 2 的幂次，便于 log2 和除法计算

### 参考经验摘要
- 历史模式: 存储器扩展标准计算题——给定容量和芯片规格求芯片数
- 难度锚点: K1=3,K2=3,K3=3 与题位难度目标 2 一致
- 典型陷阱:
  - 字扩展倍数与位扩展倍数相加而非相乘
  - 混淆地址线和数据线的决定因素
  - 芯片容量 K×位 的读取错误
