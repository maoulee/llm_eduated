## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 栈队列和数组 > 数组和特殊矩阵
- primary_target_name: 二维数组列优先存储的地址计算
- question_type: single_choice
- examination_mode: 计算型——地址公式应用

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 单步列优先地址公式代入计算，K2为主导难度，涉及非2幂常规乘法/加法；K4有常规注意点（列优先识别、下标起始约定）

### 结构要求
- option_count: 4
- distractor_strategy: 行优先公式结果 / 下标起始约定错误 / 行列下标互换
- condition_count: 3~4

### 参数约束
- rows（行数）: 5~12，非2的幂，rows≠cols
- cols（列数）: 5~12，非2的幂，rows≠cols
- base（基地址）: 100~10000整数，能被elem_size整除
- elem_size（元素大小）: 2或4或8字节
- 目标元素下标(i,j): i∈[1,rows-2], j∈[1,cols-2]（0起始），非首非末元素
- 一致性要求: 正确答案≠行优先结果≠下标±1结果≠行列互换结果（四选项互不相同）

### 参考经验摘要
- 历史模式: 列优先地址公式代入计算，经典选择题考法
- 难度锚点: K2=3主导（非2幂常规计算），K4=2（存储顺序与下标约定）
- 典型陷阱: 行优先与列优先混淆 / 下标起始约定错误 / 行列下标互换 / 忘记乘元素大小
