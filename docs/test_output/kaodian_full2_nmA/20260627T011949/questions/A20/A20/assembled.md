## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: 输入输出 > 综合
- primary_target_name: I/O 系统综合（中断/DMA 对比与时间计算）
- question_type: comprehensive
- examination_mode: 综合计算对比——给定 I/O 数据传送场景，分别计算中断方式和 DMA 方式的 CPU 时间开销并对比效率

### 难度目标
- k_target: K1=3,K2=4,K3=3,K4=4,K5=3
- difficulty_level: 4
- difficulty_rationale: K4 为主导（=4），核心区分点在于学生能否识别中断方式与 DMA 方式在 CPU 介入机制上的本质差异，并据此选择正确计算路径。K2=4 因涉及多步非 2 幂次计算和单位换算。整体定位为中等偏上难度综合题。

### 结构要求
- sub_question_count: 4
- sub_question_distribution: 第1问=3分（计算中断方式CPU时间），第2问=3分（计算DMA方式CPU时间），第3问=2分（效率对比分析），第4问=2分（DMA周期窃取对CPU性能影响）
- dependency: 第1问、第2问并行独立；第3问依赖第1、2问结果；第4问与第2问相关但独立计算
- distractor_strategy: 无干扰项（综合题为计算/分析题，通过计算陷阱实现区分度）
- condition_count: 4-5

### 参数约束
- 数据块大小 D: 取值 4KB-64KB，需被每次中断传送量 d_int 整除，需被 DMA 传送单位 d_dma 整除
- 每次中断传送量 d_int: 取值 1B-4B，保证 D/d_int ≥ 1000 以体现中断方式的高频特征
- 中断响应+处理时间 t_int: 取值 1-100 μs，优先非 2 的幂
- DMA 预处理时间 t_dma_pre: 取值 1-50 μs
- DMA 后处理中断时间 t_dma_post: 取值 1-50 μs
- CPU 时钟频率 f: 取值 50-500 MHz，用于推算总线周期
- DMA 传送单位 d_dma: 等于 1 个字（4B），每次传送窃取 1 个总线周期
- 整除约束: D mod d_int = 0，D mod d_dma = 0
- 时间单位: 题干中可混合 μs/ns/MHz，考察单位统一能力

### 参考经验摘要
- 历史模式: 408 真题经典模式——给定数据块和设备参数，分别计算中断/DMA 的 CPU 时间开销并对比（2010、2014 真题模式）
- 难度锚点: K4 常在 3-4，K2 常在 3-4，核心区分点为 CPU 介入时机辨析
- 典型陷阱: ①中断次数≠数据块大小 ②DMA 的 CPU 开销≠数据传送时间 ③周期窃取按传送次数而非总时间计算 ④时间单位统一
