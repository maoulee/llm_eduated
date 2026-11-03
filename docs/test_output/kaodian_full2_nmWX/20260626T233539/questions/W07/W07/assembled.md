## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: 存储系统 > Cache
- primary_target_name: Cache 命中率与平均访问时间计算
- question_type: comprehensive
- examination_mode: 计算题——给定 Cache 命中率/缺失代价/主存周期，求平均访问时间与效率

### 难度目标
- k_target: K1=3,K2=3,K3=3,K4=2,K5=2
- difficulty_level: 3
- difficulty_rationale: 核心为 AMAT 公式链的多步计算（K3=3 主导），需记忆公式（K1=3）且代入非平凡数值（K2=3），陷阱为常规注意点（K4=2），涉及 Cache-主存层次但单向数据传递（K5=2），整体为标准难度综合计算题。

### 结构要求
- sub_question_count: 3
- sub_question_breakdown:
  - Q1: 3分，单步计算（命中率或基础 AMAT），为后续问提供数值基础
  - Q2: 4分，多步计算（平均访问时间 + 效率），依赖 Q1 结果
  - Q3: 3分，参数变化分析（改变命中率或加二级 Cache），基于 Q2 框架对比
- dependency: 串行递进（Q1→Q2→Q3）
- condition_count: 3-5
- condition_design: Cache 命中时间、主存访问周期、命中率（或可推导命中率的序列）；第 3 问附加变化参数

### 参数约束
- t_c (Cache命中时间): 1-5 时钟周期，整数
- t_m (主存访问周期): t_c 的 5-20 倍，整数
- h (命中率): 0.80-0.98，直接给定或由访问序列推导
- 缺失代价定义: 题干须明确——建议"缺失时代价为 t_m 个时钟周期"，此时 AMAT = t_c + (1-h) × t_m
- Q3 变化参数: 与 Q1/Q2 保持同量级，可设二级 Cache 或改变命中率
- 单位一致性: 所有时间统一为时钟周期

### 干扰与陷阱设计
- 公式形式陷阱: AMAT 有两种等价写法 h×t_c+(1-h)×(t_c+t_m) 与 t_c+(1-h)×t_m，学生须理解二者关系
- 效率定义区分: Cache 效率 vs 加速比，题干须明确考查哪一个
- 命中率与缺失率: 须正确转换，不可混淆

### 参考经验摘要
- 历史模式: "给参数→算AMAT→算效率→改变参数分析"递进结构
- 难度锚点: K3 主导在 3-4 区间，标准难度避免 K4 过深
- 典型陷阱: 缺失代价是否含命中时间、效率定义混淆、百分数与小数混用
