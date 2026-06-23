## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 查找 > 散列表
- primary_target_name: 给关键字序列和散列函数用拉链法构造散列表求ASL
- question_type: comprehensive
- examination_mode: 计算型——散列表构造与ASL计算

### 难度目标
- k_target: K1=2,K2=3,K3=2,K4=2,K5=1
- difficulty_level: 3
- difficulty_rationale: 需构造散列表并代入ASL公式计算，公式计算为主，轻量启发式估算

### 结构要求
- sub_question_count: 3
- sub_question_details:
  - q1: 类型=构造, 考察目标=拉链法构造散列表, 分值=4
  - q2: 类型=计算, 考察目标=查找成功ASL, 分值=3
  - q3: 类型=计算, 考察目标=查找失败ASL, 分值=3
- dependency: q1为q2/q3前置，q2与q3并行
- condition_count: 2（关键字序列、散列函数定义）

### 参数约束
- 关键字序列长度 n: 8-12，n < m（装载因子 α < 1）
- 表长 m: 11-13（质数），m > n
- 关键字值域: 0-100 的整数，互不相同
- 散列函数: H(key) = key mod m
- 冲突数: 2-5 个（保证 ASL 不退化也不繁杂）
- 链表长度分布: 不均匀（含长度 1、2、3 的链），保证 ASL 计算有区分度
- ASL_success 分母: n（关键字数）
- ASL_fail 分母: m（表长）

### 参考经验摘要
- 历史模式: 构造+ASL双问/三问结构，历年稳定
- 难度锚点: K2为主导（公式计算），K3较低（流程固定），整体难度3
- 典型陷阱:
  - 混淆ASL_success分母（应为n而非m）
  - 混淆ASL_fail分母（应为m而非n）
  - 查找失败时链表长度计数错误（应为链表长度+1）
  - 拉链法链表插入方向理解偏差
