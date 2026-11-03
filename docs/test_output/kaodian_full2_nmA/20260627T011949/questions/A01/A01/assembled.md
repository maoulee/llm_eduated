## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: 数据表示与运算 > 补码
- primary_target_name: 补码真值与范围
- question_type: single_choice
- examination_mode: 计算型——补码真值/范围判断

### 难度目标
- k_target: K1=3,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 2
- difficulty_rationale: K2 主导，需一步非平凡补码求值计算；K1=3 需准确记忆补码定义；其余维度低。整体标准难度，对应 difficulty=2。

### 结构要求
- option_count: 4（1 正确 + 3 干扰）
- distractor_strategy:
  - 干扰项1: 符号位判断错误——把负补码当正数按权展开
  - 干扰项2: 未按补码权重展开——全部按无符号正权展开
  - 干扰项3: 数值近邻——某一位权重漏算或多算，产生接近正确答案的不同值
- condition_count: 1-2（补码机器数序列 + 位数说明）

### 参数约束
- 补码位数 n: 5 ≤ n ≤ 8，建议奇数位
- 符号位: 必须为 1（负补码），提高区分度
- 真值绝对值: 非 2 的幂
- 选项互斥: 4 个选项对应 4 个不同数值，互不重合

### 参考经验摘要
- 历史模式: 无历史 question_experiences，依据 slot 与 K 定义直接规划
- 难度锚点: K2=3 为主导，对应 difficulty=2 标准选择题
- 典型陷阱: 符号位权重处理错误、补码/原码混淆、范围边界不对称（最小负数无对应正数）
