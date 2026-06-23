## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 线性表 > 单链表
- primary_target_name: 删除单链表中所有值为x的结点
- question_type: comprehensive
- examination_mode: 算法设计型——链表操作算法设计

### 难度目标
- k_target: K1=1,K2=2,K3=2,K4=3,K5=4
- difficulty_level: 4
- difficulty_rationale: 算法设计题，需自行设计完整算法（定义+思想+实现），跨模块联动需求高（K5=4），存在边界条件陷阱（K4=3）

### 结构要求
- sub_question_count: 3
- sub_question_structure:
  - Q1: 结点类型定义（2分）
  - Q2: 算法思想描述（4分）
  - Q3: C/C++代码实现含注释（8分）
- dependency: 混合（Q1独立，Q2独立，Q3依赖Q1和Q2）
- condition_count: 2-3

### 参数约束
- 链表结构: 带头结点的单链表，头指针为L
- 链表长度n: n ≥ 0，允许空表
- 待删除值x: 与结点data域同类型，取值不限
- 结点data域类型: 基本类型（int/char）
- 一致性约束: 题干链表定义与Q1结点类型一致，代码参数名与题干一致
- 可调自由度: 链表长度具体值、x具体值由Question Agent决定

### 参考经验摘要
- 历史模式: 408数据结构算法设计题标准模式——定义+思想+代码
- 难度锚点: K5主导(4)，K4=3体现边界陷阱
- 典型陷阱: 空表未处理、首元结点删除指针错误、连续匹配删除指针断裂、未释放内存、头结点处理不当
