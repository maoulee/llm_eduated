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
- difficulty_rationale: 单步公式代入计算题，需掌握列优先地址公式；计算涉及非 2 的幂次乘法存在算错空间；行优先/列优先区分和下标起始约定为常规注意点

### 结构要求
- option_count: 4
- distractor_strategy:
  - 干扰项A: 按行优先公式计算（最常见的混淆路径）
  - 干扰项B: 下标起始约定混淆（0 起始↔1 起始，偏移量差 1）
  - 干扰项C: 偏移量计算遗漏修正项或行列维度代入颠倒
  - 约束: 4 个选项值互不相同，间距 ≥ elem_size
- condition_count: 4–5
- condition_design:
  - 条件1: 数组行数 rows
  - 条件2: 数组列数 cols
  - 条件3: 基地址 base
  - 条件4: 每个元素大小 elem_size
  - 条件5: 下标起始约定（0 起始或 1 起始，明确写出）

### 参数约束
- rows: ∈ [4, 10]，至少 rows 或 cols 之一为非 2 的幂次
- cols: ∈ [4, 10]，rows ≠ cols
- base: ∈ [100, 1000]，十进制整数
- elem_size: ∈ {2, 4, 8}
- 目标元素下标: i ∈ [1, rows-2], j ∈ [1, cols-2]，保证偏移量非平凡
- 一致性约束: 正确答案与每个干扰项之差的绝对值 ≥ elem_size，确保选项不重合
- 自由度: Question Agent 在上述范围内自由选取具体值

### 参考经验摘要
- 历史模式: 列优先地址公式应用是数组和特殊矩阵章节的经典选择题考察模式，408 真题多次出现
- 难度锚点: K2=3 标准计算量，非 2 幂次乘法代入；K4=2 常规注意点（行优先/列优先、下标起始）
- 典型陷阱: 行优先与列优先混淆（最高频）、下标 0/1 起始混淆、元素大小遗漏、行列代入顺序颠倒
