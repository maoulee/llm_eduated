## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: 计算机组成原理 > CO-2 数据的表示和运算 > 定点数的运算
- primary_target_name: 补码加减运算与溢出判断
- question_type: comprehensive
- examination_mode: 计算型——补码运算与溢出判断

### 难度目标
- k_target: K1=2,K2=3,K3=3,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 计算题，需多步推演（求补码→双符号位加法→判溢出），K3主导，K2涉及非2幂次定点小数运算，整体难度中等

### 结构要求
- sub_question_count: 3
- sub_question_types: [计算, 计算, 分析]
- sub_question_scores: [3, 4, 3]
- sub_question_dependency: 串行（1→2→3）
- distractor_strategy: 不适用（计算题，无选项）
- condition_count: 2-3

### 子问题规划
- 子问题1（3分·计算）：将真值 x、y 转换为变形补码（双符号位补码）
- 子问题2（4分·计算）：用变形补码执行双符号位加法，写出运算过程和结果
- 子问题3（3分·分析）：根据双符号位状态判断是否溢出，指明溢出类型

### 参数约束
- x真值范围: [-1, +1)，绝对值建议 [0.1, 0.95]
- y真值范围: [-1, +1)，绝对值建议 [0.1, 0.95]
- 符号关系约束: 建议设计为会产生溢出的情形（同号且|x+y|≥1），核心考察溢出判断
- 小数位数n: 4或5，真值在该精度下可精确表示
- 可调自由度: Question Agent 可自由选择具体真值、小数位数，满足范围与一致性约束即可
- 一致性要求: x、y 真值在n位二进制小数下可精确表示，避免无限循环小数

### 参考经验摘要
- 历史模式: 无历史 question_experiences，依据 slot expected_form 直接规划
- 难度锚点: K3=3 主导（3-5步串行流程），K2=3（非2幂次定点小数运算）
- 典型陷阱: 负数补码双符号位转换（11 + 数值位取反加1）、双符号位进位处理、溢出判断仅看符号位一致性（00/11不溢出，01/10溢出）
