## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 栈队列和数组 > 数组和特殊矩阵
- primary_target_name: 二维数组列优先存储的地址计算
- question_type: single_choice
- examination_mode: 计算型——地址公式应用

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 单步公式代入计算题，需掌握列优先地址公式，参数设计为非2幂次增加计算量，K2为主导维度

### 结构要求
- option_count: 4
- distractor_strategy: 利用行优先公式误用、下标偏移错误、行列数混淆生成3个干扰项
- condition_count: 5（行数m、列数n、元素大小L、基地址Base、目标坐标(i,j)）

### 参数约束
- 行数 m: [3, 10]，整数
- 列数 n: [3, 10]，整数，m ≠ n（保证行优先与列优先结果不同）
- 元素大小 L: {2, 4, 8} 字节
- 基地址 Base: 4的倍数，[1000, 10000]
- 目标行下标 i: 0 < i < m-1（不取边界）
- 目标列下标 j: 0 < j < n-1（不取边界）
- 列优先公式: Loc(i,j) = Base + (j × m + i) × L
- 行优先公式（干扰）: Loc(i,j) = Base + (i × n + j) × L
- 正确答案与干扰项应有合理差距

### 参考经验摘要
- 历史模式: 地址计算是数据结构经典题型，行优先/列优先对比是常见考察方式
- 难度锚点: K2=3 为合理定位，参数设计为非2幂次增加计算量
- 典型陷阱: 行优先公式误用、下标从1开始计算、行列数m/n混淆、算术错误
