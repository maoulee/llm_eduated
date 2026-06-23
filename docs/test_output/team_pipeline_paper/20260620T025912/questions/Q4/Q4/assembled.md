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
- difficulty_rationale: 需理解next数组构造规则并代入计算，K2为主导维度（标准计算），K3较低（仅需求某一位值，不需完整构造数组）

### 结构要求
- option_count: 4
- distractor_strategy: 干扰项覆盖next数组定义版本混淆、前后缀匹配判断错误、边界条件处理错误三类典型错误路径
- condition_count: 2（1个显式模式串 + 1个隐含next数组定义，需在题干中明确）

### 参数约束
- 模式串: 长度5-8字符，小写字母a-z，需包含至少一处重复子串结构（保证next值非平凡）
- 目标位置: 模式串长度的一半到末尾之间，非首字符非末字符（避免退化）
- next数组定义: 题干中需明确给出定义，与408教材定义一致，避免自创定义
- 参数一致性: 目标位置必须在模式串有效索引范围内

### 参考经验摘要
- 历史模式: 2015_Q8、2024_Q6 均为"给定模式串求next数组某位值"的计算型题目
- 难度锚点: K2=3（标准计算），K3=2（较低推演），K1=2（较低认知）
- 典型陷阱: next数组定义版本混淆（0起始vs1起始）、前后缀匹配边界判断错误、next[j]与next[j-1]混淆
