## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 线性表 > 顺序表
- primary_target_name: 顺序表与链表的随机访问特性对比
- question_type: single_choice
- examination_mode: 概念辨析型——存储结构与随机访问特性

### 难度目标
- k_target: K1=4,K2=1,K3=1,K4=3,K5=1
- difficulty_level: 2
- difficulty_rationale: 概念辨析题，考查对顺序表与链表存储特性的理解，需精准辨析"随机访问"与"顺序访问"概念，存在陷阱词需识别

### 结构要求
- option_count: 4
- distractor_strategy: 3个干扰项分别对应：①混淆按位查找与按值查找 ②误认为链表支持随机访问 ③忽略存储密度差异
- condition_count: 1-2

### 参数约束
- 元素位置索引 i: 取值范围 i ≥ 2，避免 i=0/1 时两者访问时间差异不明显
- 无其他数值参数：本题为纯概念题

### 参考经验摘要
- 历史模式: 概念辨析型，通过对比两种数据结构特性考查理解深度
- 难度锚点: K1=4主导，K4=3辅助，整体难度2
- 典型陷阱: 混淆"按位查找"与"按值查找"、误认为链表支持随机访问、忽略存储密度差异
