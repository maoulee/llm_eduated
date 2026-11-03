## 出题契约

### 基本信息
- target_subject: 组成原理
- target_family: CO-4 指令系统 > 指令格式 > 操作码编码 > 扩展操作码
- primary_target_name: 扩展操作码
- question_type: comprehensive
- examination_mode: 计算型——扩展操作码数量计算

### 难度目标
- k_target: K1=3,K2=3,K3=2,K4=4,K5=1
- difficulty_level: 3
- difficulty_rationale: 扩展操作码需理解编码空间逐级分配机制，K4=4 主导——保留前缀计数是核心陷阱，学生若不理解扩展机制本质会得到错误结果

### 结构要求
- sub_question_count: 2
- sub_question_breakdown: Q1(3分)=计算某级指令最大数量及保留前缀数；Q2(3分)=计算下一级可扩展指令最大数量
- dependency: Q2 依赖 Q1 的保留前缀结果（串行）
- distractor_strategy: 不适用（主观题）
- condition_count: 2-3（指令字长、地址码位数、已知某类指令数量）

### 参数约束
- instruction_word_length: 取 16 或 32，须可被地址码位数整除
- address_field_bits: 取 4、6 或 8，满足 word_length ≥ 2 × address_field_bits
- format_levels: 2-3 级（如二地址→一地址→零地址）
- known_instruction_count: 满足 0 < N < 2^(opcode_bits)，且 N 非 2 的幂次（确保保留前缀数 > 1，使计算非平凡）
- consistency: 各级 opcode_bits + Σaddr_bits = word_length（总位数守恒）
- next_level_max: R × 2^(extra_addr_bits) - R_next（R 为上一级保留前缀数，R_next 为本级保留用于更下一级的前缀数）
- freedom: L、A、N_known 可自由选择，但须保证 Q2 答案为正整数且非平凡

### 参考经验摘要
- 历史模式: 扩展操作码数量计算（已知某级数量→求另一级数量），CO-4 标准考法
- 难度锚点: K4=4 对应保留前缀计数陷阱，区分度高
- 典型陷阱: ①直接用 2^opcode_bits 未减去已占用模式；②忘记保留本级扩展前缀；③混淆操作码位数与地址码位数
