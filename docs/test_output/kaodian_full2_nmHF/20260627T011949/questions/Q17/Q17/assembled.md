## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: 中央处理器 > 性能
- primary_target_name: CPI 与 MIPS 计算
- question_type: comprehensive
- examination_mode: 综合题——给指令CPI/比例表+主频，求CPI和MIPS

### 难度目标
- k_target: K1=3,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 核心考查 CPI 加权平均与 MIPS 串行计算链（K3=3），需准确记忆公式（K1=3），计算涉及非 2 幂次整数（K2=3），存在单位换算常规注意点（K4=2），单一知识点内部完成（K5=1）。整体难度 3。

### 结构要求
- sub_question_count: 3
- sub_question_details:
  - Q1: 加权平均 CPI 计算（2 分，计算题）
  - Q2: 由 CPI 和主频求 MIPS（2 分，计算题，依赖 Q1）
  - Q3: 给定总指令数求程序执行时间（2 分，计算题，依赖 Q1 或 Q2）
- dependency: 串行链式 Q1 → Q2 → Q3
- score_total: 6
- condition_count: 3（指令 CPI/比例表 + CPU 主频 + 程序总指令数）

### 参数约束
- 指令类别数: 3-5 类
- 各类 CPI: 取值 1-6，至少两类 CPI 不同，至少一类 CPI ≥ 3
- 各类使用比例: 正整数百分比，和 = 100
- 主频 f: 500MHz - 4GHz 范围，需与 CPI 配合使 MIPS 结果为非整数
- 程序总指令数 N: 10⁶ - 10⁹ 量级
- 一致性约束: 加权 CPI 结果可表示；MIPS = f/(CPI×10⁶) 结果有区分度；执行时间 = N×CPI/f 在毫秒~秒级

### 参考经验摘要
- 历史模式: CPI/比例表 + 主频 → 依次求 CPI、MIPS、执行时间，408 CPU 性能经典综合题模式
- 难度锚点: K3=3 为主，3-5 步串行计算链，路径唯一
- 典型陷阱:
  1. 主频单位换算错误（MHz/GHz/Hz）
  2. 加权平均未正确归一化
  3. MIPS 公式记忆错误
  4. 执行时间公式与 MIPS 路径混淆
