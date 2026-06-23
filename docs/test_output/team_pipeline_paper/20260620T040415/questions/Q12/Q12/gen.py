"""Dijkstra 单源最短路径算法模拟"""

INF = float('inf')

# 邻接矩阵（∞ 表示无直接边）
adj = [
    [INF, 2, 5, INF, INF, INF],  # V0
    [INF, INF, 1, 4, INF, INF],  # V1
    [INF, INF, INF, 2, 6, INF],  # V2
    [INF, INF, INF, INF, 1, 3],  # V3
    [INF, INF, INF, INF, INF, INF],  # V4
    [INF, INF, INF, INF, INF, INF],  # V5
]

n = 6
source = 0

def dijkstra(adj, n, source):
    dist = [INF] * n
    dist[source] = 0
    S = [False] * n
    rounds_dist = []  # 记录每轮结束后的 dist
    
    # 第 0 轮：初始化
    print(f"\n第 0 轮（初始化）：dist = {dist}")
    rounds_dist.append(list(dist))
    
    # 第 1~6 轮：6 次迭代
    non_trivial_count = 0
    for round_idx in range(n):
        # 选 dist 最小且不在 S 中的顶点
        u = -1
        min_d = INF
        for v in range(n):
            if not S[v] and dist[v] < min_d:
                min_d = dist[v]
                u = v
        
        if u == -1:
            break
        
        S[u] = True
        print(f"\n第 {round_idx + 1} 轮：选中 V{u}（dist={dist[u]}），加入 S 集合")
        
        # 松弛操作
        updated = False
        for v in range(n):
            if not S[v] and adj[u][v] != INF:
                new_dist = dist[u] + adj[u][v]
                if new_dist < dist[v]:
                    dist[v] = new_dist
                    updated = True
        
        if updated:
            non_trivial_count += 1
        
        print(f"  松弛后 dist = {dist}")
        rounds_dist.append(list(dist))
    
    return dist, rounds_dist, non_trivial_count

# 执行 Dijkstra
final_dist, rounds_dist, non_trivial_count = dijkstra(adj, n, source)

# 打印每轮 dist 数组（子问1）
print("\n" + "="*60)
print("【子问1】每轮 dist 数组")
print("="*60)
print(f"{'轮次':<8}", end="")
for i in range(n):
    print(f"V{i:<5}", end="")
print()
for i in range(n + 1):
    print(f"第{i}轮:  ", end="")
    vals = rounds_dist[i]
    for v in vals:
        if v == INF:
            print(f"∞   ", end="")
        else:
            print(f"{v:<5}", end="")
    print()

# 打印最终最短路径（子问2）
print("\n" + "="*60)
print("【子问2】源点 V0 到各顶点的最短路径长度")
print("="*60)
for i in range(1, n):
    if final_dist[i] == INF:
        print(f"V0 → V{i}: ∞（不可达）")
    else:
        print(f"V0 → V{i}: {final_dist[i]}")

# ========== 验证段：通过条件翻译为 assert ==========

# 条件1：至少 4 轮非平凡松弛
assert non_trivial_count >= 4, f"非平凡松弛轮数={non_trivial_count}，应≥4"

# 条件2：至少有一个顶点的最短路径经过 ≥2 条边
# 检查：该顶点的 dist ≠ 直接边权（即不是单条边直达）
has_multi_edge = False
for v in range(1, n):
    if adj[source][v] != INF and final_dist[v] != adj[source][v]:
        has_multi_edge = True
        break
    elif adj[source][v] == INF and final_dist[v] != INF:
        # 无直接边但可达，必然经过 ≥2 条边
        has_multi_edge = True
        break
assert has_multi_edge, "不存在经过≥2条边的最短路径"

# 条件3：存在迂回路径（直接边权 > 经其他顶点的路径权值和）
has_detour = False
for v in range(1, n):
    if adj[source][v] != INF and final_dist[v] < adj[source][v]:
        has_detour = True
        break
assert has_detour, "不存在迂回路径（绕路更短的情况）"

print("\n✅ 所有通过条件验证通过")
