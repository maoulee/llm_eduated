## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度（WPL）
- question_type: single_choice
- examination_mode: 给定遍历序列+叶子权值 → 还原树结构 → 计算 WPL

### 难度目标
- k_target: K1=2,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 以 WPL 定义理解和遍历序列还原树结构为核心，计算量适中。K2（理解）和 K3（应用）为主要区分维度，干扰项围绕路径长度计数方式、内部节点误入等经典陷阱设计。

### 结构要求
- option_count: 4
- distractor_strategy: |
    干扰项需覆盖以下至少 3 种策略：
    A. 路径长度计数偏移：边数误算为节点数（每叶路径长度 +1）
    B. 内部节点误入：所有节点（含内部节点）参与加权求和
    C. 特定叶子深度错误：某叶子归入相邻层导致该叶子路径长度 ±1
    D. 权值分配错位：不同叶子的权值与深度错位配对
- condition_count: 2
- condition_spec: |
    条件1：二叉树的遍历序列（前序+中序 或 层序+前序），用于唯一确定树结构
    条件2：各叶子节点的权值分配

### 参数约束
- leaf_count: 4-6 个，与遍历序列推导出的树结构一致
- tree_depth: 3-4 层（根为第 0 层），至少存在两个不同深度的叶子
- leaf_weights: 1-9 的正整数，各叶子权值互不相同
- traversal_type: 前序+中序 或 层序+前序（须能唯一确定二叉树）
- internal_nodes: 内部节点无权值，不参与 WPL 计算

### 参考经验摘要
- 历史模式: 408 真题 WPL 选择题典型框架为"给结构+给权值→算 WPL"，参考 2014、2017 年类似题位
- 难度锚点: K2/K3 为主区分维度；选择题中 K1/K4/K5 通常较低
- 典型陷阱: |
    1. 根的路径长度为 0 而非 1
    2. WPL（带权路径长度）与 PL（路径长度）混淆
    3. 内部节点误参与 WPL 计算
    4. 不对称树形态下叶子深度确定错误
