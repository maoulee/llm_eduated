## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 线性表 > 单链表
- primary_target_name: 单链表递归逆序输出函数填空并说明功能
- question_type: comprehensive
- examination_mode: 代码阅读型——链表递归函数分析

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 代码阅读题，需理解递归函数逻辑填空（K2=3），递归流程步数有限（K3=2），单链表知识点内部闭环（K5=1）

### 结构要求
- sub_question_count: 2
  - 第1问：填空题，3分，填写2处空白语句使函数正确实现逆序输出
  - 第2问：简答题，2分，简述该递归函数的功能
  - 依赖关系：串行，第2问依赖第1问
- distractor_strategy: 不适用（非选择题）
- condition_count: 1段C语言递归函数代码（含2-3处空白）+ 链表结点结构体定义

### 参数约束
- 结构体定义: LNode 标准定义，int data + struct LNode *next
- 函数签名: void func(LNode *p) 或等价形式，函数名不暴露功能意图
- 空白1: 递归调用语句，形如 func(p->next); 函数名须与签名一致
- 空白2: 访问/输出语句，形如 printf("%d ", p->data); 输出格式可调
- 空白排列约束: 先递归后访问 → 逆序输出（核心逻辑）
- 终止条件: if (p==NULL) return; 可作为已知或设为空白
- 空白总数: 2-3处，可调
- 自由度: 函数名、变量名、输出格式、空白数量均可由出题者调整

### 参考经验摘要
- 历史模式: 链表递归函数填空+功能描述，408经典综合题考法
- 难度锚点: K2=3主导，整体难度3，属标准综合题
- 典型陷阱: 递归调用与访问语句的先后顺序决定顺序/逆序输出；考生混淆先后则功能判断错误
