## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: CO-3 > 存储系统 > 主存储器和CPU的连接
- primary_target_name: 存储器地址线/数据线计算
- question_type: single_choice
- examination_mode: 计算型——存储容量推导

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 2
- difficulty_rationale: 需一步推导，地址线→寻址空间×数据位宽；核心计算为 2 的幂乘法加单位换算，整体偏简单但需准确

### 结构要求
- option_count: 4
- distractor_strategy: |
    干扰1: bit/Byte 混淆（差8倍）
    干扰2: 忽略数据线位宽（只算 2^n）
    干扰3: 幂次算错或单位换算错（差2倍或4倍）
    要求三干扰项数值互不相同且与正确答案不同
- condition_count: 2~3
- score: 2

### 参数约束
- 地址线位数 n: 10 ≤ n ≤ 20，正整数
- 数据线位数 m: m ∈ {4, 8, 16, 32}
- 总容量: 2^n × m (bit)，由 n、m 唯一确定
- 选项统一单位: 四选项须用同一容量单位（bit 或 Byte）
- 一致性要求: 正确答案 = 2^n × m bit 经单位换算后的值；各干扰项须对应不同错误路径且数值互不重合

### 参考经验摘要
- 历史模式: 给定地址线和数据线数量反推存储容量，是存储系统章节经典选择题考法
- 难度锚点: K2 主导（3级），核心在一步乘法+单位换算
- 典型陷阱: bit/Byte未换算、忽略数据线位宽、2的幂计算错误
