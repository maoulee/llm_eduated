## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 串 > 串的模式匹配
- primary_target_name: KMP算法中next数组的某一位值计算
- question_type: single_choice
- examination_mode: 计算型——next数组求解

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 需理解next数组构造规则并代入计算，K2为主导维度，涉及非平凡的前后缀比对

### 结构要求
- option_count: 4
- distractor_strategy: 干扰项应覆盖典型错误路径：(1) next数组定义版本混淆导致的偏移值 (2) 最长相等前后缀识别错误（漏掉更长前后缀）(3) 索引混淆（0-based vs 1-based）(4) 将next值与nextval值混淆
- condition_count: 2（模式串 + 目标位置）

### 参数约束
- 模式串长度: 6-10字符，应包含重复子串结构使next值非平凡
- 模式串字符集: 建议使用小写字母或简单字符组合
- 目标位置索引: 2 ≤ j ≤ len-2，避免边界平凡值
- 目标位置next值范围: 2-4，保证有区分度
- 参数间一致性: 模式串结构需保证目标位置的next值在指定范围内，且不同错误路径产生不同结果

### 参考经验摘要
- 历史模式: 2015_Q8、2024_Q6均为"给定模式串求next数组某位值"的计算型题目
- 难度锚点: K2=3为主导，K3=2为辅助，符合"代入计算+轻量推演"定位
- 典型陷阱: next数组定义版本混淆、索引0/1起始混淆、最长相等前后缀识别错误、next与nextval混淆
