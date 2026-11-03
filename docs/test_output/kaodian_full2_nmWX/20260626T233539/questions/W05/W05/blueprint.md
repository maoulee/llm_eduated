## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: 数据表示与运算 > 补码
- primary_target_name: 变形补码加减运算与溢出判断
- question_type: comprehensive
- examination_mode: 计算题——给定两个定点小数，用变形补码计算 x+y 和 x-y 并判断溢出

### 难度目标
- k_target: K1=3,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: K3为主导维度（标准流程推演3-5步），整体难度3。变形补码加减运算流程明确，溢出判断需准确运用双符号位规则，符合标准难度综合题定位。

### 结构要求
- sub_question_count: 3
- sub_question_details:
  - (1) 求x和y的变形补码，2分，计算题
  - (2) 变形补码计算x+y并判断溢出，4分，计算题
  - (3) 变形补码计算x-y并判断溢出，4分，计算题
- dependency: (1)→(2),(3) 串并行混合
- condition_count: 2（x和y两个定点小数的值）

### 参数约束
- x: 定点小数，十进制或分数形式，绝对值范围 (0.1, 0.8)
- y: 定点小数，十进制或分数形式，绝对值范围 (0.1, 0.8)
- overflow_requirement: x+y 和 x-y 中至少一组运算结果溢出（双符号位不一致），另一组不溢出
- binary_length: x、y的小数部分二进制表示建议4-6位，避免过度繁琐
- sign_combination: 可选正+正溢出、负+负溢出、正-负溢出、负-正溢出等组合，由Question Agent确定
- consistency: x和y的符号与大小组合必须保证溢出需求成立

### 参考经验摘要
- 历史模式: 变形补码运算为408经典考法，核心考察双符号位编码与溢出判读
- 难度锚点: K3=3标准流程推演，步数适中，K1=3需准确记忆变形补码定义
- 典型陷阱: x-y需先求[-y]变补；混淆变形补码与普通补码符号位数；溢出判断时未区分01上溢与10下溢
