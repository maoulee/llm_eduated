## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 排序 > 交换排序
- primary_target_name: 给定序列用快速排序求前两趟划分结果
- question_type: single_choice
- examination_mode: 计算型——快速排序过程模拟

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 4
- difficulty_rationale: 需手动模拟快速排序partition过程，多步计算，轻量启发式估算

### 结构要求
- option_count: 4
- distractor_strategy: 干扰项应覆盖典型错误路径：基准位置错、指针移动顺序错、第二趟划分范围错、单趟结果正确但第二趟错误
- condition_count: 2（初始序列 + 基准选择规则）

### 参数约束
- 序列长度: 8-12 个元素，保证前两趟划分有足够区分度
- 元素值: 互异正整数，范围 1-20
- 基准选择规则: 必须明确指定（首元素/尾元素/中间元素）
- 一致性约束: 第一趟划分后基准左侧<基准、右侧>基准；第二趟划分范围必须是第一趟产生的子序列
- 可调自由度: 序列具体元素值、长度、基准选择方式均可调整

### 参考经验摘要
- 历史模式: simulation_00180.md 快速排序过程模拟，考察 partition 手动执行
- 难度锚点: K2 为主导维度（标准计算），K3 较低（路径唯一），K1/K4 较低
- 典型陷阱: 基准最终位置错、指针移动顺序混淆、第二趟划分范围错
