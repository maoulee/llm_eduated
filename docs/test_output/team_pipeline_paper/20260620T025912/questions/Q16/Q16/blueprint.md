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
- difficulty_rationale: 代码阅读题，需理解递归函数逻辑填空并描述功能，K2主导

### 结构要求
- sub_question_count: 2
- sub_question_1: 代码填空，3分，填补递归函数关键语句
- sub_question_2: 功能简述，2分，用一句话说明函数功能
- dependency: 并行（两问独立）
- condition_count: 1段递归函数代码（含结构体定义）

### 参数约束
- 链表节点数: 3-5个，便于手动追踪递归过程
- 递归函数行数: 5-8行（不含结构体定义）
- 空白数量: 1-2处，位于关键逻辑点（递归终止条件 / 递归调用 / 回溯操作）
- 函数签名: 标准形式 void PrintReverse(LinkList L) 或类似
- 代码风格: C语言风格，符合考研教材惯例
- 递归结构: 必须包含递归终止条件、递归调用、回溯阶段操作三个部分

### 参考经验摘要
- 历史模式: 代码阅读型是数据结构常见题型，侧重理解而非手写
- 难度锚点: K2=3主导，递归理解是核心难点
- 典型陷阱: 混淆"先输出再递归"（正序）与"先递归再输出"（逆序）；递归终止条件写错（L->next==NULL vs L==NULL）
