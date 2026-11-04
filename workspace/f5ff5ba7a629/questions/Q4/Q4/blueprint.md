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
- difficulty_rationale: 需理解next数组构造规则并代入计算，核心区分在K2=3的单步代入计算准确度，整体难度中等偏下

### 结构要求
- option_count: 4
- distractor_strategy: ①next值±1（长度与下标混淆）；②取较短非零匹配值（忽略"最长"）；③给出nextval值混淆（若该位next≠nextval）
- condition_count: 2（模式串 + 求解位置）

### 参数约束
- 模式串: 长度6~10个小写字母；约束——指定求解位置j处，P[0..j-1]存在长度≥2的相等前后缀（next[j]非退化值）
- 求解位置j: 4~(n-1)，n为模式串长度；约束——next[j]的目标值在2~4之间
- next数组约定: 408统考定义，next[0]=0, next[1]=1
- 选项: 0~5之间的整数值，4个选项互不相同

### 参考经验摘要
- 历史模式: 2015年第8题、2024年第6题均为"给定模式串求next数组指定位值"的计算型选择题，模式稳定
- 难度锚点: K2=3为该题位核心区分维度，K1=2/K3=2/K4=2/K5=1
- 典型陷阱: ①教材约定差异（next[0]/next[1]取值）；②忽略"最长"取短匹配；③next与nextval混淆
