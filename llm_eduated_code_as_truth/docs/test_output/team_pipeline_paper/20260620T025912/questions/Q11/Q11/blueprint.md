## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 树与二叉树 > 二叉树遍历
- primary_target_name: 给后序+中序还原二叉树写出先序序列
- question_type: comprehensive
- examination_mode: 推演型——遍历序列还原二叉树

### 难度目标
- k_target: K1=1,K2=2,K3=4,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 需多步递归推导还原二叉树结构，机制推演为主（K3=4），基础概念和计算需求低

### 结构要求
- sub_question_count: 2
- condition_count: 2（后序序列、中序序列）
- score_distribution: 子问题1（5-6分）+ 子问题2（4-5分）

### 参数约束
- 节点数 n: 6 ≤ n ≤ 10，保证推演步数 >5 步
- 树结构: 非退化、非完全平衡，左右子树均存在且规模≥2
- 节点标签: 大写字母 A-J，任意分配
- 序列一致性: 后序和中序必须来自同一二叉树，由 gen.py 生成保证

### 参考经验摘要
- 历史模式: 2012_Q3、2026_Q3 均为后序+中序还原二叉树写出先序
- 难度锚点: K3=4 为典型，多步递归推演是核心
- 典型陷阱: 混淆遍历性质、递归边界错误、先序输出顺序错误
