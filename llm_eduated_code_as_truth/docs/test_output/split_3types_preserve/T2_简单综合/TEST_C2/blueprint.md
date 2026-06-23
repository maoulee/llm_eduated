## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树遍历序列还原
- question_type: comprehensive
- examination_mode: 序列还原 + 性质分析

### 难度目标
- k_target: K1=3,K2=3,K3=3,K4=2,K5=3
- difficulty_level: 3
- difficulty_rationale: medium难度，涉及四种遍历的综合运用，需要理解遍历本质而非死记硬背

### 结构要求
- sub_question_count: 2-3
- sub_question_structure:
  - Q1: 还原二叉树（构造/画图），40-50%分值
  - Q2: 写出其他遍历序列（计算），30-40%分值
  - Q3: 分析树的性质（分析），10-20%分值（可选）
- dependency: 串行（Q2、Q3依赖Q1）
- condition_count: 2（两种遍历序列）

### 参数约束
- 节点数 n: 5-10，建议 6-8
- 树高 h: 2-4，需满足 h ≥ ⌈log₂(n+1)⌉
- 给定遍历类型: 前序+中序 或 后序+中序（必须包含中序）
- 序列唯一性: 给定的两种遍历序列必须能唯一确定二叉树
- 结构约束: 非纯链状，应有分支
- 叶子节点数: 2-4
- 度为2的节点数: 1-3

### 参考经验摘要
- 历史模式: 给两种遍历→还原树→求第三种遍历，偶尔加入树的性质分析
- 难度锚点: medium难度对应节点数6-8，树高3左右，子问题2-3个
- 典型陷阱: 混淆前序/后序根节点位置、子树划分错误、层序遍历层次顺序错误
