## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 栈队列和数组 > 循环队列
- primary_target_name: 循环队列入队/出队操作代码填空
- question_type: comprehensive
- examination_mode: 代码补全型——循环队列操作实现

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 代码补全题，需理解循环队列操作逻辑填入正确语句，K2为主导（取模运算理解）

### 结构要求
- sub_question_count: 1（代码填空型综合题，通过多个填空位置构成考察单元）
- blank_count: 3-5（填空数量）
- blank_strategy: 覆盖判满/判空条件、指针更新语句、元素存取操作
- condition_count: 1（给出完整结构定义和函数框架）

### 参数约束
- maxsize: 取值范围 [10, 100]，建议非 2 的幂，使取模运算非平凡
- front_initial: 通常为 0
- rear_initial: 通常为 0（空队列时 front == rear）
- element_type: int 或 char 等基础类型
- 一致性约束: 判满条件 (rear+1)%maxsize == front 与判空条件 front == rear 必须兼容；指针更新必须使用取模运算

### 参考经验摘要
- 历史模式: 2011_Q3、2014_Q3 均为循环队列代码填空，考查入队/出队操作实现
- 难度锚点: K2=3（主导），K3=2，整体难度 3
- 典型陷阱: 判满条件未考虑循环（rear == maxsize-1）、指针更新忘记取模、front/rear 更新方向错误
