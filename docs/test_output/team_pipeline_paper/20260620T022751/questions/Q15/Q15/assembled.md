## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 栈队列和数组 > 循环队列
- primary_target_name: 循环队列入队/出队操作代码填空
- question_type: comprehensive
- examination_mode: 代码补全型——循环队列操作实现

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 代码补全题，需理解循环队列操作逻辑填入正确语句，K2为主导维度（取模运算代入），其余维度均为较低水平

### 结构要求
- sub_question_count: 1（代码填空题，按填空点划分考察维度）
- blank_count: 3-4（填空点数量）
- blank_strategy: 每个空考察独立知识点（判满/判空/元素操作/指针更新/返回值），填空点之间弱依赖
- condition_count: 1（函数框架作为唯一显式条件）

### 参数约束
- MAXSIZE: 取值范围 [5, 10]，整数，不宜为 2 的幂（避免取模退化）
- front_initial: 固定为 0
- rear_initial: 固定为 0
- operation_type: EnQueue 或 DeQueue 二选一
- consistency: 判满必须使用 (rear+1)%MAXSIZE==front（少用一个单元策略），更新必须使用取模运算

### 参考经验摘要
- 历史模式: 2011_Q3、2014_Q3 均为循环队列代码填空，考察入队/出队操作的关键语句
- 难度锚点: K2=3 为主导，K1/K3/K4=2，K5=1
- 典型陷阱: 判满与判空混淆、忘记取模、未考虑循环特性、判满策略与更新策略不一致
