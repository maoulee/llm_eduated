## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: CO-3 存储系统 > 高速缓冲存储器 Cache
- primary_target_name: Cache全相联映射分析
- question_type: comprehensive
- examination_mode: 分析型——Cache地址映射与数据装入

### 难度目标
- k_target: K1=2,K2=3,K3=4,K4=3,K5=1
- difficulty_level: 3
- difficulty_rationale: 分析题，需理解全相联映射机制并对多个地址逐步推演命中/装入/替换结果，K3主导（多步串行推演+Cache行状态维护），K4=3（全相联Tag构成与直接映射的混淆陷阱）

### 结构要求
- sub_question_count: 3
- sub_question_breakdown:
  - SQ1: 计算题（3分）——Cache行数、地址分解（块号位数/块内地址位数）、Tag构成
  - SQ2: 分析题（4分）——给定地址序列，逐个分析命中/未命中、装入行号、替换
  - SQ3: 分析题（3分）——最终Cache行Tag与数据内容、或命中率计算
- dependency: SQ1→SQ2→SQ3 串行依赖
- distractor_strategy: 无（分析题，无选项干扰；难点在于推演准确性）

### 参数约束
- Cache总容量 C: 2KB~8KB, 2的幂次
- Cache行长 L: 32B 或 64B
- Cache行数 N=C/L: 2的幂次, 范围32~256
- 主存地址位数 A: 16~24
- 块内地址位数 b=log2(L): 5或6
- 主存块号位数 m=A-b: 由A和b决定
- 全相联Tag: =主存块号(m位)
- 访问地址序列: 4~6个地址, 至少1对块号相同(命中), 多数块号不同(装入)
- 初始Cache: 全空
- 替换策略: FIFO(题干明确指定)
- 一致性要求: 所有地址的十六进制值须在地址空间范围内; 序列设计须保证至少1次命中和1次替换场景

### 参考经验摘要
- 历史模式: Cache映射分析标准模式——参数分解→逐地址分析命中/装入→状态总结
- 难度锚点: K3=4对应4-6个地址的多步推演+状态表维护; K4=3对应全相联Tag=全部块号的混淆陷阱
- 典型陷阱: 1)全相联Tag=主存块号(非去掉行号); 2)块内地址位数由行长决定; 3)命中比较Tag非完整地址; 4)替换策略仅Cache满时触发
