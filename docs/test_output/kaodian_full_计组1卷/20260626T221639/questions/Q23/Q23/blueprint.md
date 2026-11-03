## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: CO-2 > 数据的表示和运算 > 算术逻辑单元ALU > 加法器
- primary_target_name: 先行进位加法器
- question_type: subjective（简答题）
- examination_mode: 推导型——先行进位原理

### 难度目标
- k_target: K1=3,K2=2,K3=4,K4=2,K5=2
- difficulty_level: 3
- difficulty_rationale: 需推导先行进位公式（Gi/Pi定义→C1~C4递归展开→原理解释），多步串行推导步数>5，对工作记忆有明确要求；K3为主导维度

### 结构要求
- sub_question_count: 3
- sub_question_details:
  - (1) 定义推导：写出 Gi/Pi 定义并解释含义，2分
  - (2) 多步推导：递归展开 C1、C2（仅含 C0 和各组 Gi/Pi），2分
  - (3) 多步推导+阐释：展开 C3 或 C4，说明先行进位消除行波延迟的原理，2分
- dependency: 串行 (1)→(2)→(3)
- condition_count: 1组核心条件（四位CLA输入输出描述+进位递推起始式）
- distractor_strategy: 不适用（主观题）

### 参数约束
- 无数值参数：纯符号推导题
- 符号一致性约束:
  - 进位递推关系统一形式：Ci = Gi + Pi·Ci-1
  - Gi = Ai·Bi（进位生成函数，全题统一）
  - Pi 由 Question Agent 选择 Pi = Ai⊕Bi 或 Pi = Ai+Bi，全题保持一致
- 自由度:
  - Pi 定义形式（异或版/或版）由 Question Agent 决定
  - 第(3)问展开目标可选 C3 或 C4
  - 各子问分值可在±1分范围内微调

### 参考经验摘要
- 历史模式: 无历史经验（reference_questions 为空），考察模式来自 slot examination_mode
- 难度锚点: K3=4 对应 5+步递归展开，是本题核心区分度
- 典型陷阱: 学生可能写出含 C1 的 C2 表达式而未完全展开——题干应明确要求"仅以 C0 和各组 Gi/Pi 表示"
