## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: CO-7 输入输出系统 > I/O方式
- primary_target_name: 中断I/O方式可行性分析
- question_type: comprehensive（分析题）
- examination_mode: 分析型——I/O方式性能计算与判断

### 难度目标
- k_target: K1=2,K2=4,K3=3,K4=3,K5=2
- difficulty_level: 3
- difficulty_rationale: 分析题，核心是公式计算（时钟周期→中断耗时→比较传输率），K2/K3并重。K2=4为主导维度，多级单位换算是区分度核心；K3=3需走完固定3-5步流程；K4=3存在可行性判断方向的隐含前提陷阱。

### 结构要求
- sub_question_count: 3
- total_score: 10
- sub_question_distribution:
  - Q1: 计算题，3分——CPU时钟周期及中断服务时间计算
  - Q2: 计算+分析题，4分——外设A数据到达间隔与中断服务时间比较，可行性判断
  - Q3: 分析题，3分——外设B（高传输率）可行性对比分析
- condition_count: 3-4
- dependency: 串行（Q1→Q2→Q3，Q1结果为Q2/Q3提供基础数据）

### 参数约束
- cpu_clock_freq: 取值范围 100MHz-500MHz，要求换算后时钟周期为简洁纳秒值
- isr_cycle_count: 取值范围 200-2000 cycles
- device_A_data_rate: 取值范围 1-50 KB/s，约束 T_arrival_A > T_ISR（中断I/O可行）
- device_B_data_rate: 取值范围 0.5-5 MB/s，约束 T_arrival_B < T_ISR（中断I/O不可行）
- consistency_constraint:
  - T_ISR = isr_cycle_count / cpu_clock_freq
  - T_arrival = 1 / data_rate（按字节粒度换算）
  - 两设备结论须有明显差距，非临界值
  - 参数选择需使数值计算涉及非2幂次除法，体现K2=4的换算难度

### 参考经验摘要
- 历史模式: 中断I/O可行性分析——计算中断服务耗时，比较数据到达间隔，判断可行性。经典CO-7综合题型。
- 难度锚点: K2=4主导，多级单位换算（Hz→s、B/s→间隔、cycles→s）为区分度核心；K3=3固定流程3-5步；K4=3可行性判断方向陷阱。
- 典型陷阱: 数据到达间隔与传输率换算方向混淆（间隔≠传输率本身）；可行性条件方向搞反（服务时间<到达间隔才可行）；忽略数据粒度（字节vs比特）。
