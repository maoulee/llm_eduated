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
- difficulty_rationale: 需手动模拟Dijkstra算法多轮松弛过程，长程推演，维持dist数组和S集合的动态状态更新

### 结构要求
- sub_question_count: 2
- sub_question_1: 类型=推演计算, 分值=6, 考察目标=逐趟dist数组更新过程
- sub_question_2: 类型=计算结果, 分值=4, 考察目标=最终最短路径长度及路径
- dependency: 串行（子问题2依赖子问题1）
- condition_count: 2-3（图的表示、源点指定、算法要求）

### 参数约束
- 顶点数 n: 5-7个，命名为v1,v2,...,vn或v0,v1,...,v(n-1)
- 边数 m: 8-12条，保证图连通
- 权重 w: 正整数，范围2-10，不宜全部相同
- 图类型: 有向带权图
- 连通性: 从源点出发能到达所有顶点
- 源点: 明确指定（如v1），建议选在图的"一端"
- 路径多样性: 存在多条路径到达同一顶点，保证松弛操作有意义

### 参考经验摘要
- 历史模式: Dijkstra手工模拟是图算法题经典考察方式，逐趟写dist数组是标准做法
- 难度锚点: K3=4为核心，顶点数5-7是经验值，权重2-10保证计算友好
- 典型陷阱: 负权边（应避免）、不连通图（应保证连通）、dist初始化错误、松弛条件判断错误、路径回溯错误
