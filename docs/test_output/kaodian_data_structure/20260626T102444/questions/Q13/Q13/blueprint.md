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
- difficulty_rationale: 需构造散列表并代入ASL公式计算，公式计算为主，轻量构造推导；查找成功与失败ASL分母不同需注意

### 结构要求
- sub_question_count: 3
- sub_questions:
  - Q1（约4分）：构造拉链法散列表，写出各散列地址及链表
  - Q2（约3分）：计算查找成功的平均查找长度 ASL_success
  - Q3（约3分）：计算查找失败的平均查找长度 ASL_failure
- dependency: Q1 为基础，Q2/Q3 依赖 Q1 的构造结果
- condition_count: 3-4（关键字序列、散列函数、表长/模值、拉链法说明）
- distractor_strategy: 不适用（综合题无选项干扰）

### 参数约束
- 关键字个数 n: 7-10 个正整数
- 散列表长度 m: 略大于 n（如 m=11），保证有空地址
- 模值 p: p ≤ m，取不大于 m 的质数
- 冲突约束: 至少 2 个关键字映射到同一散列地址（至少一个链表长度 ≥ 2）
- 空地址约束: 至少 1 个散列地址为空（链表长度 0）
- 均匀性约束: 不应出现关键字集中到 1-2 个地址的极端分布
- 可调自由度: Question Agent 自由选择具体关键字序列和 p 值，满足上述约束即可

### 参考经验摘要
- 历史模式: 散列表综合题标准模式——构造+ASL(成功)+ASL(失败)
- 难度锚点: K2=3（ASL代入含非整除），K4=2（分母差异常规注意点）
- 典型陷阱:
  1. 查找成功ASL分母=n（关键字个数），查找失败ASL分母=p（散列表长度），易混淆
  2. 拉链法查找失败时每个地址比较次数=该链表长度
  3. 链表内比较次数从链表头算起到目标节点
