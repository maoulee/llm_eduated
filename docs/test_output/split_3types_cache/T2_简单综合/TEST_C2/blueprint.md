## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树遍历序列还原
- question_type: comprehensive
- examination_mode: 序列还原 → 性质求解

### 难度目标
- k_target: K1=3,K2=4,K3=3,K4=4,K5=2
- difficulty_level: 3
- difficulty_rationale: medium难度，考察经典还原方法，节点数适中，思维复杂度较高但题型标准

### 结构要求
- sub_question_count: 2
- sub_question_1: 类型=计算/构造, 考察目标=遍历序列还原二叉树, 分值=6
- sub_question_2: 类型=分析/计算, 考察目标=树的性质求解, 分值=4
- dependency: 串行（第2问依赖第1问结果）
- condition_count: 2

### 参数约束
- 节点数 n: 6 ≤ n ≤ 10, 整数
- 树深度 d: 3 ≤ d ≤ 4
- 遍历序列组合: 前序+中序 或 后序+中序（必须能唯一确定二叉树）
- 叶子节点数: ≥ 2
- 结构约束: 至少一个节点有左右孩子；不能是退化链；不能是完全二叉树
- 序列元素: 互不相同的字符或数字
- 一致性: 两种遍历序列必须对应同一棵二叉树

### 参考经验摘要
- 历史模式: 给两序求一序 / 给两序画树 → 求性质
- 难度锚点: K2=4（深度理解遍历与结构关系）, K4=4（递归思维+逻辑推理）
- 典型陷阱: 根节点位置混淆、左右子树边界错误、忽略空子树、数错叶子/深度
