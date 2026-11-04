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
- difficulty_rationale: 核心在于准确记忆next数组递推规则并代入指定位置计算，K2主导，需单步公式代入且涉及非平凡整数运算，整体中等偏轻

### 结构要求
- option_count: 4
- distractor_strategy: 三种典型错误路径各产生不同数值——(1)忘记+1得next值-1；(2)off-by-one下标偏移；(3)位置混淆取相邻位值。四选项必须互不重合。
- condition_count: 2

### 参数约束
- 模式串长度n: 6≤n≤8，使用小写英文字母a–z
- 指定位置j: 3≤j≤n，避开next[1]=0和next[2]=1的平凡情况
- 前缀重复结构: 保证next[j]≥3（即P[1..k]=P[j-k..j-1]中k≥2），使正确答案非平凡
- 正确选项值: ≥3
- 干扰项约束: 四个选项必须互不相同，每个干扰项对应一种独立错误路径

### 参考经验摘要
- 历史模式: 2015 Q8、2024 Q6均为"给定模式串求next数组指定位"的计算型选择题，模式高度稳定
- 难度锚点: K2主导(K2=3)，K1=2，K3=2，整体难度2-3级
- 典型陷阱: next下标起始约定(+1问题)、off-by-one下标偏移、next与nextval混淆
