## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 线性表 > 单链表
- primary_target_name: 单链表逆序输出函数填空并说明功能
- question_type: comprehensive
- examination_mode: 代码阅读型——链表递归函数分析

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 代码阅读题，需理解递归函数逻辑填空并描述功能，轻量启发式估算

### 结构要求
- sub_question_count: 2
- sub_question_1: 代码填空（3分），填补递归函数中的关键语句
- sub_question_2: 功能简述（2分），描述函数整体功能
- condition_count: 2（链表结构定义 + 含空白的递归函数代码）

### 参数约束
- 链表节点结构: 标准结构（data域 + next指针），data类型可为int或char
- 递归函数参数: 链表头指针（LinkList/ListNode*）
- 空白数量: 1-2个（递归调用语句或输出语句位置）
- 递归终止条件: 代码中已给出（if(p == NULL) return），不作为填空
- 代码行数: 函数体5-8行（含注释），保持简洁
- 一致性约束: 空白位置必须是递归逆序输出的关键语句（递归调用或输出语句），不能是终止条件

### 参考经验摘要
- 历史模式: 代码阅读型是数据结构高频题型，递归函数分析是经典考点
- 难度锚点: K2=3为标准难度，需理解递归执行流程但不需复杂计算
- 典型陷阱: 学生可能混淆"先输出后递归"（正序）与"先递归后输出"（逆序）；功能描述可能过于笼统
