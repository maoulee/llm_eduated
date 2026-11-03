## 出题契约

### 基本信息
- target_subject: 组成原理
- target_family: CO-3 存储系统 > 主存储器和CPU的连接 > 主存容量扩展
- primary_target_name: 存储器扩展（字位同时扩展）
- question_type: comprehensive
- examination_mode: 计算型——存储器扩展芯片数量

### 难度目标
- k_target: K1=3,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 2
- difficulty_rationale: 需理解字位同时扩展原理并做芯片分组计算，计算路径固定3-5步，涉及非2幂次常规计算，无深陷阱、无跨域联动

### 结构要求
- sub_question_count: 3
- sub_question_types: [计算型, 计算型, 计算型]
- sub_question_scores: [2, 2, 2]
- dependency: 串行（子问题1 → 子问题2 → 子问题3）
- distractor_strategy: 不适用（主观题）
- condition_count: 2-3

### 子问题定义
- SQ1（2分）: 计算目标存储器地址线数量和数据线数量
- SQ2（2分）: 计算芯片组数（字扩展倍数）和每组芯片数（位扩展倍数）
- SQ3（2分）: 计算芯片总数 = 组数 × 每组芯片数

### 参数约束
- C_target（目标存储器容量）: 16KB~64KB范围
- W_chip（芯片字数）: ∈ {1K, 2K, 4K, 8K}
- B_chip（芯片位宽）: ∈ {4, 8}
- B_target（目标数据位宽）: ∈ {8, 16}，且 B_target > B_chip
- 整除约束: B_target % B_chip == 0 AND 目标字数 % W_chip == 0
- 芯片组数 G = 目标字数 / W_chip，G ≥ 2
- 每组芯片数 P = B_target / B_chip，P ≥ 2
- 总芯片数 = G × P，范围 4~64
- Question Agent 可在上述约束内自由选择具体数值

### 参考经验摘要
- 历史模式: 字位同时扩展——给定芯片规格和目标容量，计算芯片数量
- 难度锚点: K1=3/K2=3/K3=3，标准应用题，计算路径固定3-5步
- 典型陷阱: 字扩展与位扩展倍数算反；芯片规格中字数与位宽混淆；总芯片数只算一个维度
