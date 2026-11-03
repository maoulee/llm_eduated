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
- difficulty_rationale: 需多步递归推导还原二叉树结构（节点数7-11，递归深度≥3层），机制推演为主导（K3=4），仅需基本遍历定义入题（K1=1），无跨域联动（K5=1）

### 结构要求
- sub_question_count: 2
- sub_questions:
  - Q1: 分析/推演，写出还原后的二叉树结构，6分
  - Q2: 计算/推导，写出先序遍历序列，4分，依赖Q1
- dependency: serial
- distractor_strategy: 不适用（综合题非选择题）
- condition_count: 2（后序遍历序列 + 中序遍历序列）

### 参数约束
- node_count: 7 ≤ n ≤ 11
- node_identifier: 唯一大写字母（A-Z）
- tree_structure: 至少3个内部节点同时拥有左右子树；不退化为单链；度1连续链不超过2个节点
- sequence_consistency: 后序与中序序列必须由同一棵二叉树导出
- generation_method: 先构造合法二叉树，再导出后序和中序序列，保证一致性
- freedom: Question Agent 自由选择具体字母和树形态，满足结构约束即可

### 参考经验摘要
- 历史模式: 后序+中序还原二叉树为二叉树综合题高频考法，2012真题中有类似题型
- 难度锚点: K3主导（4），节点数7-11对应递归深度3-4层，推演步数10-20步
- 典型陷阱: 后序根在末尾（非开头）；中序左右子树边界划分；先序根左右顺序
