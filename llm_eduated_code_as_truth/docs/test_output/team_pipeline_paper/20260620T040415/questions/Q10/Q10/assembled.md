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
- distractor_strategy: 干扰项围绕常见错误路径设计：①第一趟对第二趟错（划错子序列） ②基准位置错 ③交换顺序错
- condition_count: 2（初始序列 + partition规则）

### 参数约束
- 序列长度: 8-12个元素，保证两趟划分有足够操作空间
- 元素值: 互不相同的整数，范围10-99，避免等差/等比等规律序列
- 基准选择规则: 必须明确指定（第一个/最后一个/中间元素），题干中写明
- 指针移动规则: 需明确左右指针移动方向和终止条件
- 一致性要求: 序列元素互异，基准规则与指针规则匹配

### 参考经验摘要
- 历史模式: simulation_00180.md，快速排序过程模拟，考察多趟partition
- 难度锚点: K2=3标准计算，K3=2推演步数适中
- 典型陷阱: 基准规则不明确、指针移动顺序混淆、第二趟子序列范围搞错、基准未放最终位置
