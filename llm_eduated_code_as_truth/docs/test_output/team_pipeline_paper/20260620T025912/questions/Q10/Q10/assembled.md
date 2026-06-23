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
- difficulty_rationale: 需手动模拟快速排序 partition 过程，多步计算，K2 为主导维度

### 结构要求
- option_count: 4
- distractor_strategy: 干扰项应覆盖典型错误路径：①基准选择错误 ②第二趟只对一个子区间 partition ③指针移动规则错误 ④排序方向搞反
- condition_count: 1（初始序列）+ 隐含条件（基准规则、排序方向）

### 参数约束
- 序列长度 n: 8 ≤ n ≤ 12，保证第二趟 partition 有区分度且计算量适中
- 元素值范围: 1 ≤ 元素值 ≤ 100，元素互不相同，序列非有序/逆序
- 基准选择规则: 题干必须明确指定（第一个/最后一个/中间元素），全程一致
- 排序方向: 题干必须明确指定（升序或降序）
- partition 算法版本: 需明确左右指针移动规则和基准归位方式
- 参数一致性: 序列长度与元素值需保证前两趟 partition 后结果有区分度，不同错误路径产生不同结果

### 参考经验摘要
- 历史模式: simulation_00180.md，快速排序过程模拟，考察 partition 过程
- 难度锚点: K2=3（partition 计算）为主导，K3=2（多步推演）为辅助
- 典型陷阱: 基准选择错误、第二趟漏掉一个子区间、指针移动规则错误、基准归位位置错误、排序方向搞反
