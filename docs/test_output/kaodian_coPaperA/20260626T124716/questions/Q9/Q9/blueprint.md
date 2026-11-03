## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: 计算机组成原理 > CO-3 存储系统 > 高速缓冲存储器 Cache
- primary_target_name: Cache全相联映射分析
- question_type: comprehensive
- examination_mode: 分析型——Cache地址映射与数据装入

### 难度目标
- k_target: K1=2,K2=3,K3=4,K4=3,K5=1
- difficulty_level: 3
- difficulty_rationale: K3主导，需按全相联映射规则对访存序列进行多步推演（>5步）并维护Cache动态状态；K2涉及地址位数和命中率的常规计算；K4存在映射方式误用的陷阱（全相联无组号/行号字段）

### 结构要求
- sub_question_count: 3
- sub_questions:
  - Q1: 计算，主存地址分解（偏移位数、块号位数、Tag位数与含义），3分
  - Q2: 分析，访存序列逐块装入Cache的映射过程（各行Tag、有效位、替换情况），5分
  - Q3: 计算，Cache命中率，2分
- dependency: 串行（Q1→Q2→Q3）
- distractor_strategy: N/A（综合题无干扰选项）

### 参数约束
- 主存容量 M: 2^16 ~ 2^24 字节，需为2的幂次
- 块大小 B: 2^4 ~ 2^7 字节，需为2的幂次
- Cache行数 L: 4-8行
- 一致性约束: M/B ≥ L 且 M/B 远大于 L（保证替换分析有意义）；偏移位数=log2(B)；块号位数=log2(M/B)；Tag位数=块号位数（全相联映射特征）
- 访存序列长度: 6-10个地址
  - 至少1个地址重复≥2次（产生命中）
  - 访问的不同主存块数 > L（触发至少1次替换）
  - 地址格式统一（字节地址或块号），与Q1地址分解一致
- 替换算法: LRU 或 FIFO，题干需明确指定
- 可调自由度: Question Agent可在上述范围内自由选择具体参数值和访存序列

### 参考经验摘要
- 历史模式: 无历史reference_questions（k_source=heuristic）；采用经典三段式结构（地址分解→逐步装入分析→命中率计算）
- 难度锚点: K3=4主导（多步推演+状态维护），对标原卷分析题常规难度
- 典型陷阱: 全相联映射下Tag=整个块号（无组号/行号字段），学生易误用直接映射或组相联映射的地址分解方式；替换分析需跟踪Cache当前各行状态
