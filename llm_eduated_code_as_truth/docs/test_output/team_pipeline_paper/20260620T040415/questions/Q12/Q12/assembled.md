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
- difficulty_rationale: 需手动模拟Dijkstra算法多轮松弛过程，长程推演，轻量启发式估算

### 结构要求
- sub_question_count: 2
- sub_question_1: 类型=推演/计算, 分值=7, 考察目标=逐趟dist数组更新过程
- sub_question_2: 类型=结果提取, 分值=3, 考察目标=源点到各顶点最短路径长度
- dependency: 弱依赖（第2问可基于第1问结果，也可独立计算）
- condition_count: 2（图的表示 + 源点指定）

### 参数约束
- 顶点数 n: 5 ≤ n ≤ 8，建议 6-7 个
- 边数 m: 足够产生至少 4-5 轮非平凡松弛
- 边权 w: 正整数，1 ≤ w ≤ 10
- 源点 s: 明确指定，建议编号较小顶点
- 图连通性: 源点应能到达所有顶点
- 一致性约束1: 边权全为正（Dijkstra适用前提）
- 一致性约束2: 至少存在一个顶点，其最短路径需经过 ≥2 条边（保证非平凡）
- 一致性约束3: 图应有迂回路径，避免所有最短路径都是直接边

### 参考经验摘要
- 历史模式: Dijkstra手工模拟是图应用题位经典模式，固定考察逐趟dist更新
- 难度锚点: K3=4为该题位典型难度，核心区分度在推演过程准确性
- 典型陷阱: 已选入S的顶点被错误更新、无穷大处理不当、选最小dist时忽略S集合状态、邻接矩阵行/列混淆
