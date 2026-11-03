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
- difficulty_rationale: 需分别推导直接映射/四路组相联/全相联三种映射方式的地址字段位数，每种映射需3-4步推演，合计步数>5步，K3为主导维度

### 结构要求
- sub_question_count: 4（直接映射2分 + 四路组相联3分 + 全相联2分 + 格式汇总1分）
- distractor_strategy: N/A（主观题，无干扰项）
- condition_count: 3-4（主存容量、Cache容量、块长；组相联需额外给出路数4）

### 参数约束
- 主存容量 M: 2²⁰B ~ 2³²B，须为2的幂
- Cache容量 C: 2¹⁰B ~ 2²⁰B，须为2的幂
- 块长 B: 2⁴B ~ 2⁸B，须为2的幂
- 组相联路数: 固定为4（四路组相联）
- 一致性约束: M > C；C > B；C/B ≥ 4（保证组相联至少有1组）
- 自由度: Question Agent在上述范围内自选具体数值，保证标记位≥4、块内地址位数4~8

### 参考经验摘要
- 历史模式: 2009_Q14、2022_Q16——给定容量参数后设计三种映射的地址格式，经典推演型考法
- 难度锚点: K3=4为主导，对应三种映射各需多步推演
- 典型陷阱: 直接映射标记位数计算易漏行号位；组相联组数=行数/路数易混淆；全相联无索引位易误加
