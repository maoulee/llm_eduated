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
- distractor_strategy: 干扰项围绕常见错误路径：partition规则理解错误（指针移动方向/交换时机）、只做了第一趟划分、基准选择错误、第二趟划分顺序错误
- condition_count: 2（给定序列 + partition规则说明）

### 参数约束
- 序列长度: 6 ≤ n ≤ 10，保证前两趟划分有足够的操作空间
- 序列元素: 整数，10 ≤ 元素值 ≤ 99，元素互不相同
- 基准选择规则: 需明确指定（如第一个元素或最后一个元素）
- partition方案: 需明确指定（如Lomuto方案或Hoare方案），避免歧义
- 一致性约束: 第一趟划分后基准左侧元素数≥2且右侧元素数≥2；序列不应是有序或逆序的

### 参考经验摘要
- 历史模式: simulation_00180.md，快速排序过程模拟，给定序列→模拟partition→写出结果
- 难度锚点: K2主导（partition过程中的比较和交换操作），K3较低（前两趟划分步数可控）
- 典型陷阱: partition规则理解错误、只做了第一趟、基准选择错误、第二趟划分顺序错误
