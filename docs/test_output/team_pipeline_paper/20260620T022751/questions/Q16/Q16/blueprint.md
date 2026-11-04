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
- difficulty_rationale: 代码阅读题，需理解递归函数逻辑填空并描述功能，K2主导（代码逻辑分析），K3较低（递归推演步数少）

### 结构要求
- sub_question_count: 2
- sub_question_1: 代码填空，约3分，1-2处填空
- sub_question_2: 功能简述，约2分
- condition_count: 1段递归函数代码（含填空）

### 参数约束
- 链表结点结构: 标准结构（data + next指针），无需自定义字段
- 递归函数签名: 给定函数名和参数（LinkList L 或 LNode *p）
- 填空位置: 递归基条件处 + 递归调用/回溯输出处，两处填空应位于递归不同阶段
- 填空数量: 1-2处
- 代码完整性: 除填空外代码结构完整可运行
- 链表长度: 3-6个结点（题干可给出示例辅助理解）

### 参考经验摘要
- 历史模式: 代码阅读+填空是数据结构高频考察模式，递归函数分析是链表章节经典题型
- 难度锚点: K2=3主导（代码逻辑分析），K3=2（递归推演2-3步）
- 典型陷阱: 递归基条件错误（L->next==NULL vs L==NULL）、混淆递归调用与回溯阶段顺序、功能描述不完整（遗漏"逆序"）
