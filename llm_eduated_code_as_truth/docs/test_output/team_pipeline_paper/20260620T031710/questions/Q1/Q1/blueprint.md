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
- difficulty_rationale: 概念辨析题，考查对顺序表与链表存储特性的理解，轻量启发式估算

### 结构要求
- option_count: 4
- distractor_strategy: 3个干扰项分别对应：①混淆随机访问与顺序访问 ②误认为链表支持O(1)访问 ③将查找与随机访问混为一谈
- condition_count: 1-2

### 参数约束
- 本题为纯概念辨析题，无强制数值参数
- 若引入场景参数：表长 n ≥ 2，元素位置 i 为合法索引
- 参数自由度：Question Agent 可自主决定是否引入具体场景参数

### 参考经验摘要
- 历史模式: simulation_00049.md 中的概念辨析题模式——对比两种数据结构/算法特性
- 难度锚点: K1=4（概念辨析典型值），K2/K3/K5=1（无计算/推演/跨域）
- 典型陷阱: 混淆随机访问与顺序访问定义、误认为链表支持O(1)访问、将查找与随机访问混为一谈
