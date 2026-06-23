"""Dijkstra 算法手工模拟 —— 题干→代码翻译"""

INF = float('inf')

# 邻接矩阵（题干直接翻译）
adj = [
    [INF, 4, 1, INF, INF, INF],  # v0
    [INF, INF, 2, 1, INF, INF],  # v1
    [INF, 3, INF, 5, 6, INF],    # v2
    [INF, INF, INF, INF, 2, 6],  # v3
    [INF, INF, INF, INF, INF, 3],# v4
    [INF, INF, INF, INF, INF, INF],# v5
]

n = len(adj)  # 6 个顶点
source = 0    # v0 为源点


def dijkstra(adj, n, source):
    """逐趟模拟 Dijkstra 算法，返回每轮状态和最终 dist"""
    dist = [INF] * n
    dist[source] = 0
    visited = [False] * n
    rounds = []  # 每轮记录：(选中顶点, 松弛次数, 更新后的dist副本)
    relaxation_count = 0  # 实质性 dist 更新次数

    for round_idx in range(n):
        # 选 dist 最小且未访问的顶点
        u = -1
        min_d = INF
        for i in range(n):
            if not visited[i] and dist[i] < min_d:
                min_d = dist[i]
                u = i

        visited[u] = True
        round_relax = 0

        # 对 u 的所有出边执行松弛
        for v in range(n):
            w = adj[u][v]
            if w != INF and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                relaxation_count += 1
                round_relax += 1

        rounds.append((u, round_relax, list(dist)))

    return dist, rounds, relaxation_count


# 执行
final_dist, rounds, relaxation_count = dijkstra(adj, n, source)

# 打印推演过程
print("=== Dijkstra 逐趟推演 ===")
print(f"初始 dist: {[0] + [INF]*(n-1)}")
for i, (u, relax, d) in enumerate(rounds):
    d_str = [str(x) if x != INF else '∞' for x in d]
    print(f"第{i+1}轮: 选中 v{u}, 松弛{relax}次, dist = [{', '.join(d_str)}]")
print(f"\n最终 dist: {final_dist}")
print(f"总实质性松弛次数: {relaxation_count}")

# ========== 通过条件 → assert ==========

# 条件1: 连通性 —— 最终 dist 全部有限
assert all(d < INF for d in final_dist), \
    f"连通性失败: dist 中存在 ∞ → {final_dist}"

# 条件2: 非平凡松弛 —— 至少 2 次实质性 dist 更新
assert relaxation_count >= 2, \
    f"非平凡松弛失败: 仅 {relaxation_count} 次更新，需 ≥ 2"

# 条件3: 推演轮数 —— 共 6 轮（等于顶点数）
assert len(rounds) == n, \
    f"推演轮数失败: {len(rounds)} 轮，需 {n} 轮"

# 条件4: Dijkstra 正确性 —— 三角不等式
for u in range(n):
    for v in range(n):
        w = adj[u][v]
        if w != INF:
            assert final_dist[v] <= final_dist[u] + w, \
                f"三角不等式失败: dist[v{v}]={final_dist[v]} > dist[v{u}]+w={final_dist[u]}+{w}"

print("\n✅ 所有通过条件验证通过")
