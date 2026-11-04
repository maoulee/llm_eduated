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
- difficulty_rationale: 需构造散列表并代入ASL公式计算，公式计算为主（K2主导），流程推演较轻（K3=2），无跨域联动（K5=1）

### 结构要求
- sub_question_count: 2
- sub_question_1: 类型=构造/计算, 考察目标=拉链法构造散列表, 分值=4
- sub_question_2: 类型=计算, 考察目标=ASL成功与失败计算, 分值=6
- dependency: 串行（第2问依赖第1问的散列表结构）
- condition_count: 2（关键字序列、散列函数定义）

### 参数约束
- 关键字序列长度 n: 8 ≤ n ≤ 12，各元素为正整数且互不相同
- 表长 m: 质数，7 ≤ m ≤ 11，且 m < n
- 散列函数: H(key) = key mod m（除留余数法）
- 冲突数量: 3-5个（通过调整关键字序列控制）
- 一致性约束: 关键字 mod m 后应有3-5个冲突；ASL计算结果为分数或有限小数

### 参考经验摘要
- 历史模式: 408数据结构散列表题位固定为"构造+ASL计算"模式
- 难度锚点: K2为主导（计算型），K3辅助（流程推演），整体难度3
- 典型陷阱: ASL失败分母为表长m而非n；链表插入顺序（头插法）；同链不同位置查找长度不同
