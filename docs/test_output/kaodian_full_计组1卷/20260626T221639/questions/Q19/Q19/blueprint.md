## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: CO-4 > 指令系统 > 指令格式 > 操作码编码
- primary_target_name: 扩展操作码
- question_type: fill_blank
- examination_mode: 计算型——扩展操作码计算

### 难度目标
- k_target: K1=2,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 2
- difficulty_rationale: 需多步推导扩展操作码的预留编码逻辑，从二地址→一地址→零地址逐级计算，路径唯一但步骤3-5步，运算涉及2的幂次。

### 结构要求
- sub_question_count: 1（填空题，单一空）
- answer_format: 一个正整数（零地址指令最大条数）
- distractor_strategy: 填空题无干扰项；需确保答案唯一且非平凡
- condition_count: 2-3个（指令总长度、地址码位数、二地址/一地址指令条数）

### 参数约束
- 指令总长度 L: 16~24位，建议16位
- 地址码位数 addr_len: 4~8位，需满足 L - 2×addr_len ≥ 4（保证操作码至少4位）
- 二地址指令条数 N2: 0 < N2 < 2^(L-2×addr_len)，建议取该空间的1/4~3/4
- 一地址指令条数 N1: 0 < N1 < (2^(L-2×addr_len) - N2) × 2^addr_len
- 零地址指令最大条数（答案）: ((2^(L-2×addr_len) - N2) × 2^addr_len - N1) × 2^addr_len，必须为正整数
- 一致性约束: 三级预留计算均需参与（不可退化为单级或双级）
- 可调自由度: L、addr_len、N2、N1 由 Question Agent 在约束范围内选定

### 参考经验摘要
- 历史模式: 扩展操作码计算为408经典考法，形式为给定指令长度和各级指令条数求某级最大条数
- 难度锚点: K3主导（多步串行推导），K2辅助（幂次运算），整体难度2
- 典型陷阱: 忽略每级预留编码需乘以地址码扩展倍数，直接做减法
