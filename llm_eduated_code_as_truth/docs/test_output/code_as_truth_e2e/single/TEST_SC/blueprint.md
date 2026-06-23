## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: DS-5 > 树与二叉树
- primary_target_name: 二叉树带权路径长度(WPL)
- question_type: single_choice
- examination_mode: 计算型——WPL公式计算与树结构分析

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: WPL 计算涉及多步运算（K2=3），需结合树结构分析确定路径长度（K3=2），但概念本身直接、不涉及创新（K5=1），整体定位中等偏下

### 结构要求
- option_count: 4
- distractor_strategy: 至少选用 2 种干扰方式——路径长度偏移（层数与边数混淆）、遗漏叶子、权值混淆、内部节点误计；四个选项之间最小差值 ≥ 3
- condition_count: 2
- condition_1: 二叉树完整结构（图形或无歧义的结构描述）
- condition_2: 各叶子节点权值

### 参数约束
- leaf_count: 4~6 个叶子节点
- tree_depth: 3~4 层（根为第 0 层）
- weight_range: 正整数 1~15，各叶子权值应有差异
- path_length_variety: 至少存在 2 种不同路径长度（范围 1~3）
- wpl_correct: 正整数，仅一个选项匹配
- option_spacing: 四选项间最小差值 ≥ 3，干扰项与正确值差 5~20
- tree_shape: 非完全二叉树优先，增加路径长度分析的区分度

### 参考经验摘要
- 历史模式: 给定二叉树→正向计算 WPL，选择题以正向计算为主流
- 难度锚点: K2=3 对应计算步数 4~6 步，考生平均耗时 2~3 分钟
- 典型陷阱: 路径长度定义混淆（层数 vs 边数）为最高频错误来源；其次为遗漏叶子或误计内部节点
