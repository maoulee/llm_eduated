## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树遍历序列还原
- question_type: comprehensive
- examination_mode: 经典还原模式（给定两种遍历序列还原二叉树）

### 难度目标
- k_target: K1=3,K2=3,K3=2,K4=3,K5=3
- difficulty_level: 3
- difficulty_rationale: medium难度，节点数适中，需理解遍历本质但计算量可控

### 结构要求
- sub_question_count: 2-3
- sub_question_structure:
  - Q1: 还原二叉树或求第三种遍历序列（计算/还原，5-6分）
  - Q2: 求树的深度和叶子节点数（计算/分析，4-5分）
  - Q3: 分析遍历序列唯一性条件（分析，3-4分，可选）
- dependency: 串行（Q2依赖Q1还原的树，Q3独立）
- condition_count: 2（两种遍历序列）

### 参数约束
- 节点数 n: 5 ≤ n ≤ 10
- 树高 h: 3 ≤ h ≤ 4
- 遍历序列对: 前序+中序 或 后序+中序（必须包含中序）
- 节点值: 互不相同的字符或数字
- 一致性: 两种序列对应同一棵树，序列长度均为 n，还原后树高在 [3,4] 范围内

### 参考经验摘要
- 历史模式: 给定两种遍历序列（含中序）还原二叉树，求第三种遍历或树的性质
- 难度锚点: medium难度对应 n=7-8, h=3, 2-3问
- 典型陷阱: 混淆根节点位置、左右子树边界错误、忽略中序的关键作用
