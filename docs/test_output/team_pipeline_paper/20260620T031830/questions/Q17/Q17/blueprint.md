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
- difficulty_rationale: 算法设计题，需自行设计完整算法（定义+思想+实现），K5=4为主导，删除操作改变链表结构影响后续遍历逻辑，K4=3考察边界条件陷阱

### 结构要求
- sub_question_count: 3
- sub_question_1: 结点类型定义，2分
- sub_question_2: 算法思想描述，4分
- sub_question_3: C/C++代码实现，8分
- condition_count: 2-3

### 参数约束
- 链表长度 n: 取值范围 5-15，需足够展示连续删除场景
- x 的值: 与链表中至少2个结点data值相同，且至少存在连续两个结点data值均为x
- 链表结构: 带头结点，头结点data域无意义
- 一致性约束: x必须在链表中出现，但不能所有结点都是x（避免退化）
- 可调自由度: 链表长度、x的具体值、x出现的次数和位置

### 参考经验摘要
- 历史模式: 链表操作算法设计题，标准三问结构（定义+思想+代码）
- 难度锚点: K5=4为主导，K4=3为辅助
- 典型陷阱: 连续删除时前驱指针错误后移、删除后忘记free、误删头结点、空链表/全匹配未处理
