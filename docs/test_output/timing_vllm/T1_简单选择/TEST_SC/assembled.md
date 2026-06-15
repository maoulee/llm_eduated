## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度
- question_type: single_choice
- examination_mode: 给定二叉树结构+叶子节点权值，计算WPL

### 难度目标
- k_target: K1=2,K2=3,K3=3,K4=2,K5=2
- difficulty_level: 3
- difficulty_rationale: 中等难度，涉及WPL定义理解和中等计算量，适合考查学生对基本概念和计算方法的掌握

### 结构要求
- option_count: 4
- distractor_strategy: 基于典型错误设计干扰项：(1)包含非叶子节点的计算结果 (2)路径长度从1开始计数的结果 (3)权值分配错误的结果 (4)算术错误结果
- condition_count: 2

### 参数约束
- 节点总数 N: [5, 10]，建议6-8个
- 叶子节点数 L: [3, 5]，约束 L ≤ N/2 + 1
- 树的高度 H: [3, 4]，约束 H ≥ ⌈log₂(N+1)⌉
- 叶子节点权值 w_i: [1, 20]，各权值应不同
- WPL结果范围: [20, 100]
- 一致性约束: 仅叶子节点有权值；路径长度从根节点开始为0；WPL = Σ(w_i × path_length_i)

### 参考经验摘要
- 历史模式: 给出二叉树图形+权值表，要求计算WPL；或给出权值集合构造哈夫曼树
- 难度锚点: K1=2,K2=3,K3=3,K4=2,K5=2 为中等难度WPL题典型分布；3-5个叶子节点为标准配置
- 典型陷阱: 非叶子节点误算、路径长度起点错误、权值分配混淆、算术错误、哈夫曼概念混淆
