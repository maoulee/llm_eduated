## 出题契约

### 基本信息
- target_subject: 数据结构
- target_family: 数据结构 > 图 > 图的应用
- primary_target_name: 给定有向带权图用Dijkstra求单源最短路径
- question_type: comprehensive
- examination_mode: 推演型——Dijkstra算法手工模拟

### 难度目标
- k_target: K1=1,K2=2,K3=4,K4=2,K5=1
- difficulty_level: 4
- difficulty_rationale: 需手动模拟Dijkstra算法多轮松弛过程，维持dist数组动态状态，推演步数>5步，中间错一步后续全错

### 结构要求
- sub_question_count: 3
- sub_question_details:
  - q1: 类型=推演, 分值=4, 考察目标=逐轮dist数组更新过程
  - q2: 类型=计算, 分值=3, 考察目标=源点到各顶点最短路径长度
  - q3: 类型=分析, 分值=3, 考察目标=源点到指定顶点的最短路径（顶点序列）
- dependency: 串行（q3依赖q2，q1独立但为q2提供基础）
- condition_count: 2（图的表示 + 源点指定）

### 参数约束
- 顶点数 n: 取值范围 5-7，建议6个（v0-v5）
- 边数 m: 取值范围 8-12
- 权重 w: 正整数，取值范围 1-15，各边权重应有差异
- 源点 s: 固定指定一个顶点（如v0）
- 目标顶点 t: 非源点，建议选距离源点较远者（路径≥3条边）
- 一致性约束:
  - 有向图
  - 从源点可达所有顶点（连通性）
  - 无负权边
  - 无自环
  - 避免平行边

### 参考经验摘要
- 历史模式: Dijkstra手工模拟为图算法题标准考察方式，核心在维持dist数组动态状态
- 难度锚点: K3=4为核心难度，6顶点10边左右可保证推演步数合理
- 典型陷阱: 已确定顶点不再松弛、选择最小dist与松弛邻接的顺序混淆、多轮更新遗漏邻接顶点、∞的处理
