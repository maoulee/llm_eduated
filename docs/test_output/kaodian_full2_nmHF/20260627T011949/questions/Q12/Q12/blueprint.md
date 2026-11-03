## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: 总线 > 带宽
- primary_target_name: 总线带宽计算
- question_type: single_choice
- examination_mode: 计算型——总线带宽=宽度×频率

### 难度目标
- k_target: K1=3,K2=3,K3=1,K4=2,K5=1
- difficulty_level: 2
- difficulty_rationale: slot 指定 target_difficulty=2，K2 为主维度取标准值3；K1 取3因必须记忆带宽公式；其余维度低位以匹配标准偏低整体难度

### 结构要求
- option_count: 4
- distractor_strategy: 三条干扰路径——(1) 忘记÷8单位换算得8倍正确值 (2) MHz/GHz混淆致数量级偏差 (3) 公式混淆(W×8/F)；四选项互不重合
- condition_count: 2（总线宽度 + 总线工作频率）

### 参数约束
- 总线宽度 W (bit): 16 / 32 / 64 三选一，必须为8的整数倍
- 总线工作频率 F (MHz): 50–800，取常规工程值，允许非2的幂
- 带宽结果 B = F × (W/8): 须为正整数 MB/s，范围约 100–8000
- 一致性要求: W 与 F 的组合必须使 B 为整洁整数，且三个干扰路径的值与正确值互不相同

### 参考经验摘要
- 历史模式: 408真题高频考法——给出总线宽度和工作频率求带宽，模式高度统一
- 难度锚点: K2 历史分布集中在2–3，本题取3
- 典型陷阱: 总线宽度以bit给出，学生常忽略÷8换算为Byte
