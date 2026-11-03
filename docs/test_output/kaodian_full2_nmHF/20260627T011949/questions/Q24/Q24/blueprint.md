## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: 存储系统 > 存储器扩展
- primary_target_name: DRAM 芯片扩展设计（芯片数/地址分配/片选/刷新）
- question_type: comprehensive
- examination_mode: 设计题——用小容量 DRAM 芯片设计大容量存储器：推导芯片数量、地址分配、片选逻辑（文字描述），并算异步刷新周期

### 难度目标
- k_target: K1=3,K2=3,K3=3,K4=4,K5=2
- difficulty_level: 4
- difficulty_rationale: K4 为主导（4分），核心难点在于位扩展/字扩展组合判断、地址线划分、刷新公式选择等隐含前提；其余维度配合设定。整体属中等偏难设计题。

### 结构要求
- sub_question_count: 4
- sub_question_breakdown:
  - Q1(3分): 计算——位扩展数、字扩展数、总芯片数
  - Q2(3分): 分析——地址线划分+各芯片组地址范围
  - Q3(2分): 分析——片选逻辑文字描述
  - Q4(2分): 计算——异步刷新信号周期
- dependency: Q1→Q2→Q3 串行；Q4 独立
- condition_count: 4（CPU地址总线宽度、数据总线宽度、DRAM芯片规格、刷新参数）
- hard_constraint: 纯文字推导，禁止要求画存储器框图/连接图

### 参数约束
- cpu_address_width: 16~24位，= 片内地址位数 + 片选地址位数
- data_bus_width: 16或32位
- dram_chip_spec: 以"字数×位宽"给出；位宽∈{1,2,4,8}且整除data_bus_width；字数为2的幂（2^10~2^20）
- bit_expansion_count: = data_bus_width / 芯片位宽，须≥2
- word_expansion_count: = 目标字数 / 芯片字数，须≥2
- chip_select_lines: = cpu_address_width - log2(芯片字数)，须≥2
- address_multiplexing: 芯片地址位数 = 行地址位数 + 列地址位数（DRAM地址复用）
- refresh_interval: 2ms或4ms
- chip_rows: = 2^(行地址位数)，行地址位数∈7~10
- consistency: 芯片地址位数 = log2(芯片字数) = 行地址位数 + 列地址位数

### 参考经验摘要
- 历史模式: 存储器扩展设计4问链路（芯片数→地址分配→片选→刷新），CO高频考法
- 难度锚点: K4偏高（组合扩展判断+地址划分+刷新公式选择），K2/K3适中
- 典型陷阱: 位/字扩展混淆、地址复用导致地址位数算错、集中刷新vs异步刷新公式混用、片选忽略译码器
