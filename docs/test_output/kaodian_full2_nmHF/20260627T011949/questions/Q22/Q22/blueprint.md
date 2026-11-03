## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: 存储系统 > Cache 映射
- primary_target_name: Cache 直接相联/组相联映射地址字段位数推导
- question_type: comprehensive
- examination_mode: 给定主存/Cache容量与块大小及组相联路数，文字推导直接相联与组相联映射下主存地址各字段位数

### 难度目标
- k_target: K1=3,K2=2,K3=4,K4=3,K5=1
- difficulty_level: 4
- difficulty_rationale: K3 为主维度——两种映射方式下需分别推导 3 个字段位数（>5 步），且直接相联到组相联的转换需动态更新组号计算；K4 次之——组号需除以路数后取 log₂，常见易错点；K2 低因计算均为 2 的幂友好运算；K5=1 因局限于 Cache 映射单一子系统

### 结构要求
- sub_question_count: 3
- question_structure:
  - Q1(3分): 直接相联映射下 Tag/行号/块内偏移 位数计算
  - Q2(4分): 组相联映射下 Tag/组号/块内偏移 位数计算
  - Q3(3分): 比较两种映射 Tag 位数差异并解释原因
- dependency: Q1 独立 → Q2 共享 Q1 的块内偏移但需新算组号 → Q3 综合分析 Q1/Q2 结果
- condition_count: 4（主存容量、Cache容量、块大小、组相联路数）
- distractor_strategy: 不适用（综合题，非选择题）

### 参数约束
- 主存容量 M: 2 的幂，256KB ~ 4MB；约束 M ≥ 8×C
- Cache容量 C: 2 的幂，8KB ~ 64KB；约束 B | C（B 整除 C）
- 块大小 B: 2 的幂，32B ~ 128B；约束 B | C 且 B | M
- 组相联路数 W: 2 或 4；约束 W | (C/B) 且 W < C/B（保证组数 ≥2）
- 自由度: Question Agent 在上述范围和约束内自由选值
- 设计要求: 确保 W≥2 使组号位数 < 行号位数，两种映射字段划分有区分度

### 参考经验摘要
- 历史模式: 408 常考 Cache 地址字段划分，原形式为画图，此处替换为纯文字推导位数
- 难度锚点: K3=4 主导，K4=3 次之，K1=3 需辨析字段概念
- 典型陷阱:
  1. 组相联组号 = Cache 行数 / 路数，学生易忘记除以路数
  2. Tag 位数 = 主存块数位数 - 行号(组号)位数，学生易用地址总位数减
  3. 块内偏移在两种映射方式下相同，学生可能误认为不同
- hard_constraint: 纯文字推导各字段位数，禁止要求画地址划分图/框图
