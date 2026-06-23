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
- difficulty_rationale: K2为主导维度，需理解next数组构造规则并逐位计算，涉及字符串前后缀比较，非简单心算但路径唯一

### 结构要求
- option_count: 4
- distractor_strategy: 干扰项应覆盖典型错误路径：(1) next与nextval混淆产生的值 (2) 前后缀长度算错1 (3) 忘记"真前后缀"约束导致的错误值 (4) 边界搞错（把位置j本身算入前缀）
- condition_count: 2（1个显式：模式串；1个隐含：next数组定义版本，需在题干中明确）

### 参数约束
- 模式串长度: 6-10个字符，字符集为小写英文字母(a-z)
- 目标位置k: 3 ≤ k ≤ 模式串长度-1，确保next[k] ≥ 2（非平凡结果）
- 模式串设计: 必须存在至少一处长度≥2的相等真前后缀，否则无法考察计算能力
- 一致性约束: 目标位置k的next值需通过实际计算得出，不能是0或1的平凡结果
- 可调自由度: 模式串具体内容、目标位置k的具体值、字符选择

### 参考经验摘要
- 历史模式: 2015_Q8、2024_Q6均采用"给定模式串→求next某位值"模式，稳定有效
- 难度锚点: 历史K2值集中在3，K3值在2-3之间，本题K2=3、K3=2符合分布
- 典型陷阱: next数组定义版本差异、真前后缀理解偏差、前后缀边界搞错、next与nextval混淆
