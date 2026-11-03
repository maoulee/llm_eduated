## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: 中央处理器 > 综合
- primary_target_name: CPU 性能综合（CPI/MIPS/流水线）
- question_type: comprehensive
- examination_mode: 综合题——给多机CPI/频率/指令分布，综合分析性能（CPI/MIPS/加速比）

### 难度目标
- k_target: K1=3,K2=4,K3=3,K4=4,K5=3
- difficulty_level: 4
- difficulty_rationale: K4 为主维度——多机频率不同时直接比 CPI 是经典暗坑，流水线/改进方案对 CPI 的动态影响需机制理解；K2=4 因多步非2幂次计算与单位换算精度敏感

### 结构要求
- sub_question_count: 4
- sub_question_details:
  - 第1问（计算，3分）：分别计算 M1、M2 的加权平均 CPI
  - 第2问（计算，3分）：分别计算 M1、M2 的 MIPS（CPI×频率换算）
  - 第3问（分析，2分）：比较两机执行同一程序的性能，判断哪台更快（K4暗坑：频率不同不能直接比CPI）
  - 第4问（分析/计算，2分）：引入改进方案，重算CPI/MIPS或计算加速比
- dependency: 串行递进（1→2→3→4）
- distractor_strategy: N/A（综合题无选项）
- condition_count: 4-5（两机频率、指令类别-CPI表、指令频度表、改进方案参数）

### 参数约束
- f₁, f₂（时钟频率）: 1.0-4.0 GHz，f₁ ≠ f₂，差值 ≥ 0.5 GHz
- n（指令类别数）: 固定 4 类
- C₁ᵢ, C₂ᵢ（各类指令CPI）: 1-6 正整数，同机内不同类差值 ≥ 1，同类别两机CPI不完全相同
- p₁,p₂,p₃,p₄（指令频度）: 5%-60%，合计 100%，任一类不超过 60%
- 改进参数: 改进后某类指令CPI降至原值1/2~2/3，MIPS变化幅度 ≥ 10%

### 参考经验摘要
- 历史模式: CPI→MIPS→性能比较 三段式，本题增加第四问流水线/改进分析
- 难度锚点: K4=4，"频率不同不能直接比CPI"为核心暗坑
- 典型陷阱: ①直接比CPI忽略频率 ②MIPS单位换算错 ③加权CPI用算术平均 ④改进后遗漏未变类别CPI
