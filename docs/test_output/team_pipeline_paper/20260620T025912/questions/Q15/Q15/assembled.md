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
- difficulty_rationale: 代码补全题，需理解循环队列操作逻辑填入正确语句，K2主导（模运算表达式），K3/K4较低（单步推导、常规注意点）

### 结构要求
- sub_question_count: 5
- sub_question_structure: 入队函数3空(3分) + 出队函数2空(2分)
- distractor_strategy: N/A（代码填空无干扰项，但空位设计应覆盖典型错误路径：判满判空混淆、漏模运算）
- condition_count: 5个空位，每个空位缺一个关键表达式

### 参数约束
- maxsize: 取值范围5-10，整数，题干显式给出
- front初始值: 0
- rear初始值: 0
- 队列元素类型: int或char
- 判满策略: 牺牲一个存储单元，(rear+1)%maxsize == front
- rear更新: rear = (rear+1)%maxsize
- front更新: front = (front+1)%maxsize
- 判空条件: front == rear

### 参考经验摘要
- 历史模式: 2011_Q3、2014_Q3 循环队列代码填空，考察判满/判空/更新操作
- 难度锚点: K2=3主导，K3=K4=2，K5=1，整体难度3
- 典型陷阱: 判满判空混淆(rear==front)、漏模运算(rear++)、未考虑循环(rear==maxsize-1)
