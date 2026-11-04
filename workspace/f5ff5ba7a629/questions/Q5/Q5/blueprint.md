## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 树与二叉树 > 二叉树性质
- primary_target_name: 二叉树叶子结点数与度为2结点数的关系应用
- question_type: single_choice
- examination_mode: 计算型——二叉树性质应用

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 需代入二叉树结点数公式计算，轻量启发式估算；核心计算步骤存在算错可能但路径唯一

### 结构要求
- option_count: 4
- distractor_strategy: 各干扰项对应不同典型错误路径（混淆n₀与n₂方向、误用n₁代入公式、遗漏总结点分解步骤），各错误路径结果互不相同
- condition_count: 2

### 参数约束
- 总结点数 n: 7 ≤ n ≤ 127，正整数；须满足 (n - n₁ - 1) 为正偶数
- 度为1的结点数 n₁: 1 ≤ n₁ ≤ n-3，正整数
- 一致性要求: n = n₀ + n₁ + n₂，n₀ = n₂ + 1，三者须自洽且 n₀ ≥ 2
- 可调自由度: Question Agent 可选择给 n + n₁ 或给 n₂ + n₁ 作为已知条件组

### 参考经验摘要
- 历史模式: 已知总结点数和度为某值结点数求叶子结点数，是二叉树性质选择题的标准考法
- 难度锚点: K2 集中在 2-3，计算量适中，区分度好
- 典型陷阱: 混淆 n₀ 与 n₂（±1方向错）、误将 n₁ 代入 n₂ 公式、忘记总结点数包含所有度数结点
