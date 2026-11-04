# TEST_AVL 骨架设计

## 基本信息

| 字段 | 值 |
|------|-----|
| slot_id | TEST_AVL |
| question_type | comprehensive |
| score | 13 |
| examination_mode | 算法设计与分析 |
| 考点 | 单链表判断是否有环 |
| 知识域 | 数据结构-2 > 线性表 > 单链表 |
| 难度 | 4 |

## question_structure_plan

### 考察模式：算法设计与分析（综合题，13分）

**考点**：单链表判断是否有环

**复用骨架来源**：408数据结构综合题标准三段式结构（定义→思想→代码），参考往年链表算法题（如链表逆序、归并排序、两链表相交判断等）的设问范式。

### 子问设计

- **子问1（约2分）**：考**链表结点类型定义**（基础层）
  - 要求用 C/C++ 定义单链表结点数据类型
  - 参考往年问法："试定义单链表结点的数据类型"
  - 考察点：struct 定义、数据域与指针域、命名规范

- **子问2（约3分）**：考**算法基本设计思想描述**（核心层）
  - 要求文字描述判断单链表是否有环的算法思想
  - 参考往年问法："简述算法的基本设计思想"
  - 考察点：快慢指针（Floyd判圈）的核心思路、相遇即有环的判定逻辑、无环时慢指针或快指针到达末尾的终止条件

- **子问3（约8分）**：考**算法代码实现**（实现层）
  - 要求编写完整算法，关键处加注释
  - 参考往年问法："根据设计思想，采用 C 或 C++ 语言编写算法，关键之处给出注释"
  - 考察点：快慢指针初始化、循环条件、指针移动步长差异、返回值设计、边界处理（空表/单结点）

### dependency_pattern：串行依赖
- 子问1 定义的数据类型在子问3 代码中直接使用
- 子问2 描述的思想是子问3 代码实现的依据
- 三问形成"定义→思想→实现"的完整算法题链条

### 题干场景设计方向
- 给定一个单链表 L（带头结点或不带头结点均可，需在题干明确）
- 要求判断该链表是否存在环
- 存在环返回 true，不存在返回 false

### audit_focus
- **should_be**：三问结构完整（定义+思想+代码）；考察快慢指针法；代码需含关键注释
- **should_not_be**：不考察环入口查找（超出考点范围）；不要求分析复杂度（除非蓝图明确要求）；不考察其他数据结构
- **teacher_annotation 体现**：期望形式中"①定义链表结点数据类型 ②描述算法基本设计思想 ③编写算法（关键处给注释）"直接映射为三问结构

## final_machine_contract

```yaml
slot_id: TEST_AVL
question_type: comprehensive
score: 13
examination_mode: 算法设计与分析
structure:
  - sub_question: 1
    topic: 链表结点类型定义
    score_weight: ~2
    dependency: none
  - sub_question: 2
    topic: 算法基本设计思想
    score_weight: ~3
    dependency: sub_question_1
  - sub_question: 3
    topic: 算法代码实现
    score_weight: ~8
    dependency: sub_question_1, sub_question_2
dependency_pattern: serial
```
