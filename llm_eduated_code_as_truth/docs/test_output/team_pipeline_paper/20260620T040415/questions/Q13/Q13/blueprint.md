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
- difficulty_rationale: 需构造散列表并代入ASL公式计算，公式计算为主（涉及分数运算），构造流程为机械性多步操作，存在常规注意点（查找失败ASL分母）

### 结构要求
- sub_question_count: 2
- sub_question_1: 类型=构造型, 考察目标=拉链法构造散列表, 分值=4-5分
- sub_question_2: 类型=计算型, 考察目标=ASL_success和ASL_fail计算, 分值=5-6分
- dependency: 串行（子问题2依赖子问题1的散列表结构）
- condition_count: 2-3个显式条件（关键字序列、散列函数、插入方式）

### 参数约束
- 关键字序列长度 n: 8-12个，取值范围10-200的整数
- 散列表表长 m: 11/13/17（质数），m略大于或接近n（装填因子α≈0.7-1.0）
- 散列函数: H(key) = key mod m（除留余数法，p=m）
- 插入方式: 必须明确指定头插法或尾插法
- 冲突分布约束: 产生3-5个非空桶，至少2个桶有≥2个元素
- 一致性要求: 所有关键字mod m后分布在多个桶上，避免退化

### 参考经验摘要
- 历史模式: 给序列+散列函数→构造表→算ASL（标准模式）
- 难度锚点: K2=3为标准定位（分数运算），K3=2（机械流程），K4=2（常规陷阱）
- 典型陷阱: 查找失败ASL分母用n而非m、链表第k个元素查找长度算错、mod运算错误
