## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度
- question_type: single_choice
- examination_mode: 给定二叉树结构+叶子权值，计算WPL

### 难度目标
- k_target: K1=2,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: medium难度，直接应用WPL定义计算，计算量适中，不涉及哈夫曼树构造等进阶内容

### 结构要求
- option_count: 4
- distractor_strategy: 基于常见错误设计干扰项：①路径长度计数错误（从1开始而非从0）②包含非叶子节点 ③漏算叶子节点 ④权值与路径长度对应错误
- condition_count: 2

### 参数约束
- 节点总数: 8-15个，树结构合法
- 叶子节点数: 4-6个
- 树高度: 3-4层
- 叶子节点权值: 1-15之间的整数，不完全相同
- WPL结果: 30-100之间的整数
- 一致性约束: 仅叶子节点有权值，非叶子节点无权值；路径长度从根到叶子经过的边数

### 参考经验摘要
- 历史模式: 给定树结构和权值求WPL是408最经典考察方式
- 难度锚点: K2=3,K3=3对应中等计算量，不涉及综合应用
- 典型陷阱: 路径长度计数起点错误、误将非叶子节点计入、漏算叶子节点、权值与路径对应错误
