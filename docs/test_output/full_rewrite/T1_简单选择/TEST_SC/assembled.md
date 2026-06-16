## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度
- question_type: single_choice
- examination_mode: 给定二叉树结构计算WPL

### 难度目标
- k_target: K1=2,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 中等难度，考查WPL基本计算能力，需理解路径长度概念并正确应用公式

### 结构要求
- option_count: 4
- distractor_strategy: 针对路径长度计算错误、叶子结点识别错误、乘法计算错误设计干扰项
- condition_count: 2-3

### 参数约束
- leaf_count: 3 ≤ leaf_count ≤ 6，建议4-5个叶子结点
- weight_i: 1 ≤ weight_i ≤ 20，整数，各权值可不同
- path_length_i: 0 ≤ path_length_i ≤ 3，由树结构决定
- height: 3 ≤ height ≤ 4，树的高度（层数）
- WPL_result: 50 ≤ WPL ≤ 200，最终计算结果范围
- consistency: 树结构合法，所有叶子结点路径长度之和合理，WPL计算结果在目标范围内

### 参考经验摘要
- 历史模式: 给定二叉树结构（图形或数组表示），标注叶子结点权值，计算WPL
- 难度锚点: 中等难度对应4-5个叶子结点，权值1-20，WPL结果50-200
- 典型陷阱: 路径长度从1开始计数、漏算叶子结点、混淆层数与路径长度、乘法计算错误
