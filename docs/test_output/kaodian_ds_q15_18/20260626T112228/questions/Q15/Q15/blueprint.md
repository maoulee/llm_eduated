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
- difficulty_rationale: 代码填空题，学生需理解循环队列判空判满逻辑和取模指针更新，构建正确的取模表达式是主要计算负担（K2=3），每空逻辑路径短（K3=2），"牺牲一个单元"判满是常规注意点（K4=2）

### 结构要求
- sub_question_count: 4（4 个代码填空）
- sub_question_detail:
  - 空1: 入队函数判满条件, 1分, 独立
  - 空2: 入队函数 rear 指针更新, 1.5分, 依赖空1
  - 空3: 出队函数判空条件, 1分, 独立
  - 空4: 出队函数 front 指针更新, 1.5分, 依赖空3
- distractor_strategy: N/A（综合题为填空题，无干扰选项）
- condition_count: 3（结构体定义、MaxSize值、函数框架）

### 参数约束
- MaxSize: 正整数, 取值范围 [5, 50], Question Agent 自定具体值, 不要求为 2 的幂
- front_init: 0（题干给出）
- rear_init: 0（题干给出）
- 判满约定: 牺牲一个存储单元, 队满条件为 (rear+1)%MaxSize == front
- 一致性: MaxSize 值必须与函数框架取模表达式一致
- 自由度: MaxSize 具体值、入队出队函数的已有语句内容、变量命名风格

### 参考经验摘要
- 历史模式: 2011_Q3/2014_Q3 以代码实现考查队列/栈操作，强调判空判满和指针移动核心逻辑
- 难度锚点: K2=3,K3=2,K4=2 与 slot k_radar 一致
- 典型陷阱: (1)判满忘记取模 (2)判满判空条件混淆 (3)rear 指向约定不清导致指针更新写反 (4)先加后取模顺序错误
