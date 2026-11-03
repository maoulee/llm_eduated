## 出题契约

### 基本信息
- target_subject: 计算机组成原理
- target_family: CO-3 > 存储系统 > 主存储器和CPU的连接
- primary_target_name: 存储器地址线/数据线计算
- question_type: single_choice
- examination_mode: 计算型——存储容量推导

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 2
- difficulty_rationale: 需一步推导，地址线→寻址空间×数据位宽，核心卡点是 K2 代入计算和单位换算

### 结构要求
- option_count: 4
- distractor_strategy: 三个干扰项分别对应：①未除以8（bit当byte用）②地址线与数据线角色互换 ③2^n 误算为 n×2 或近似错误；各干扰项数值须互不相同且与正确答案有区分度
- condition_count: 2

### 参数约束
- 地址线根数 n: 取值 {10,12,14,16,18,20}，使 2^n 对应 1K–1M 寻址空间
- 数据线位数 m: 取值 {4,8,16,32}，优先 8 以简化字节换算
- 最终容量 = 2^n × m bit = 2^n × m/8 B，换算为 KB 或 MB 后须为整数
- n 和 m 的组合须使正确答案与各干扰项数值不重合

### 参考经验摘要
- 历史模式: "线数↔容量"双向转换，反推容量为基础经典题型
- 难度锚点: K2 主导（代入计算+换算），其余维度低
- 典型陷阱: ①位与字节混淆 ②地址线根数误当容量 ③数据线与地址线角色互换
