## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树遍历序列还原
- question_type: comprehensive
- examination_mode: 给定双序列还原 + 属性推导

### 难度目标
- k_target: K1=3,K2=3,K3=3,K4=2,K5=3
- difficulty_level: 3
- difficulty_rationale: 中等难度，考察遍历序列还原的核心能力，需多步递归推理但不涉及复杂抽象

### 结构要求
- sub_question_count: 2
- sub_question_1: {type: 计算/构造, target: 还原二叉树结构, score_range: 6-7}
- sub_question_2: {type: 计算, target: 层序遍历或树属性计算, score_range: 3-4}
- dependency: 串行（第2问依赖第1问结果）
- condition_count: 2

### 参数约束
- 节点数 n: 6 ≤ n ≤ 10, integer
- 遍历序列组合: [前序, 中序] 或 [后序, 中序]
- 节点值: n个互不相同的字符或数字
- 树结构: 左右子树均非空, 高度 2 ≤ h ≤ n-1, 至少一个度为2的节点
- 序列一致性: 两种遍历序列必须对应同一棵二叉树

### 参考经验摘要
- 历史模式: 给两序列求第三序列 / 给两序列画图
- 难度锚点: 节点数7-9, 2问, 总分10-11
- 典型陷阱: 根节点位置混淆, 递归边界错误, 层序遍历队列顺序错误, 前序+后序不能唯一确定
