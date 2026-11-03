## 出题契约

### 基本信息
- target_subject: 组成原理
- target_family: 组成原理 > CO-3 存储系统 > 高速缓冲存储器Cache > Cache地址映射
- primary_target_name: Cache地址映射格式设计
- question_type: comprehensive
- examination_mode: 推演型——Cache地址映射格式设计

### 难度目标
- k_target: K1=3,K2=3,K3=4,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 需分别推导直接映射、四路组相联、全相联三种映射方式的主存地址字段划分，三问并列推演步数>5，以机制推演（K3）为主导难度

### 结构要求
- sub_question_count: 3
- sub_question_types: (1) 计算推演-直接映射格式 (2) 计算推演-四路组相联格式 (3) 计算推演-全相联格式
- sub_question_scores: (1)=3分 (2)=3分 (3)=2分
- dependency: parallel（三问共用参数，各自独立推导）
- distractor_strategy: 不适用（主观题）
- condition_count: 3（主存容量、Cache容量、块长）+ 1（四路组相联路数=4）

### 参数约束
- 主存容量 M: 2²⁰ ~ 2³² B，必须 > Cache容量
- Cache容量 C: 2¹⁰ ~ 2²⁰ B，必须 > 块长
- 块长 B: 2⁴ ~ 2⁸ B
- Cache行数 = C / B: 必须为2的幂次且 ≥ 4
- 组数 = Cache行数 / 4: 必须为2的幂次
- 路数: 固定为4（四路组相联）
- 区分度约束: 三种映射方式下Tag位数应各不相同
- 一致性约束: 三种映射各字段位数之和 = log₂(M)

### 参考经验摘要
- 历史模式: Cache地址映射格式设计——给定容量参数划分地址字段（直接映射/组相联/全相联）
- 难度锚点: K3主导，K1/K2辅助；难度等级3
- 典型陷阱:
  - 四路组相联中路数4不占地址字段但影响组数
  - 全相联无行号/组号字段，Tag位数最大
  - 组号位数 ≠ 行号位数（基数不同）
