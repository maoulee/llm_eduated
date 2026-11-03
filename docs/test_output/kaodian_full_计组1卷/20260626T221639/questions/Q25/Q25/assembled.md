## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: CO-2 > 数据的表示和运算 > 定点数的运算 > 补码加减运算
- primary_target_name: 补码加减运算
- question_type: comprehensive (简答题，6分)
- examination_mode: 计算型——补码运算与溢出判断

### 难度目标
- k_target: K1=2,K2=3,K3=4,K4=3,K5=2
- difficulty_level: 3
- difficulty_rationale: 需实际计算8位补码加减并判断溢出，减法需转化为加法（求[-B]补），多步串行运算路径唯一，至少一问产生溢出需判断

### 结构要求
- sub_question_count: 2
- sub_question_details:
  - Q1: 计算[A+B]补并判断溢出（3分，结果2分+溢出判断1分）
  - Q2: 计算[A-B]补并判断溢出（3分，结果2分+溢出判断1分）
- dependency: 两问并行，共享输入数据，互不依赖
- condition_count: 2（A和B的补码值）+ 1隐含条件（机器字长8位）
- distractor_strategy: N/A（简答题，非选择题）

### 参数约束
- machine_word_length: 8位补码（n=8），表示范围 -128 ~ +127
- param_A:
  - 取值范围: 8位补码十六进制值（0x80 ~ 0x7F）
  - 约束: 应为负数，非平凡值（非0、非±1）
  - 自由度: Question Agent 在负数补码范围内自选
- param_B:
  - 取值范围: 8位补码十六进制值（0x80 ~ 0x7F）
  - 约束: 应为负数，非平凡值
  - 自由度: Question Agent 自选
- consistency_constraint:
  - A+B 或 A-B 中至少一个超出 [-128, +127] → 至少一个运算溢出
  - 另一个运算不溢出，形成对照
  - A和B不应为0或±1等平凡值
- design_freedom: Question Agent 自由选取具体十六进制值，只需满足上述约束

### 参考经验摘要
- 历史模式: 补码加减运算+溢出判断，给定十六进制补码求结果
- 难度锚点: K3=4（多步运算），K4=3（[-B]补求取陷阱）
- 典型陷阱:
  - 减法忘记先求[-B]补
  - 溢出判断方法选择错误
  - 十六进制直接当十进制运算忽略符号性
  - 特殊值0x80（-128）处理错误
