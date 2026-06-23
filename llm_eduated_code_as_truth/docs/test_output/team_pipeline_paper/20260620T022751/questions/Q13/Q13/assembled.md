## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 查找 > 散列表
- primary_target_name: 给关键字序列和散列函数用拉链法构造散列表求ASL
- question_type: comprehensive
- examination_mode: 计算型——散列表构造与ASL计算

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 需构造散列表并代入ASL公式计算，公式计算为主，轻量启发式估算

### 结构要求
- sub_question_count: 2
- sub_question_1: 用拉链法构造散列表，分值 4-5 分
- sub_question_2: 计算查找成功和查找失败的 ASL，分值 5-6 分
- dependency: 串行（第2问依赖第1问构造结果）
- condition_count: 2-3（关键字序列、散列函数、表长）

### 参数约束
- 关键字个数 n: 8-12，整数
- 关键字取值范围: 0-100 的整数
- 表长 m: 11-17，质数优先（11、13、17）
- 散列函数: H(key) = key mod p，p = m
- 装填因子 α = n/m: 0.5-1.0
- 冲突分布: 至少 2-4 条非空链表，最长链长度 2-4
- 参数一致性: 关键字分布应使哈希值不均匀，避免无冲突或极端冲突

### 参考经验摘要
- 历史模式: 给序列+散列函数→构造表→算ASL，经典计算型题
- 难度锚点: K2=3 为核心（ASL分数运算），K3=2（构造流程固定），K4=2（常规注意点）
- 典型陷阱: 拉链法链表插入方向、ASL失败分母取值（m而非n）、冲突链长度计数起点
