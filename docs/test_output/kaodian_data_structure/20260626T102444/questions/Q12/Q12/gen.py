"""
Dijkstra 单源最短路径手工推演 —— 建模码
题干规则逐句翻译 + 通过条件 assert 验证
"""
INF = float('inf')

# === 邻接矩阵（题干给定）===
N = 6
adj = [
    # V0  V1  V2  V3  V4  V5
    [INF, 10,  4, 15, INF, INF],  # V0
    [INF, INF, INF, INF,  6, INF],  # V1
    [INF,  3, INF,  2, INF, INF],  # V2
    [INF, INF, INF, INF,  5, INF],  # V3
    [INF, INF, INF, INF, INF, INF],  # V4
    [INF, INF, INF, INF, INF, INF],  # V5
]
SRC = 0


def dijkstra(adj, src):
    n = len(adj)
    dist = [INF] * n
    prev = [-1] * n
    visited = [False] * n
    dist[src] = 0

    rounds = []  # 每轮记录 (选入顶点, dist快照)
    relax_events = []  # 记录松弛更新事件

    for _ in range(n):
        # 翻译："每轮从未收录顶点中选取 dist 值最小的顶点"
        u = -1
        best = INF
        for v in range(n):
            if not visited[v] and dist[v] < best:
                best = dist[v]
                u = v
        if u == -1:
            break  # 无可达未收录顶点
        visited[u] = True

        # 翻译："选取后将该顶点的所有出边进行松弛操作"
        for v in range(n):
            if not visited[v] and adj[u][v] != INF:
                if dist[v] > dist[u] + adj[u][v]:
                    relax_events.append((u, v, dist[v], dist[u] + adj[u][v]))
                    dist[v] = dist[u] + adj[u][v]
                    prev[v] = u

        rounds.append((u, dist[:]))

    return dist, prev, visited, rounds, relax_events


def reconstruct_path(prev, target):
    """沿 prev 链从 target 回溯到源点，返回路径列表"""
    path = []
    cur = target
    while cur != -1:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path


# ===================== 执行 =====================
dist, prev, visited, rounds, relax_events = dijkstra(adj, SRC)

print("=" * 60)
print("PARAMS")
print("=" * 60)
print(f"顶点数 N = {N}, 源点 = V{SRC}")
print("邻接矩阵（有向边）:")
for i in range(N):
    row = []
    for j in range(N):
        if adj[i][j] != INF:
            row.append(f"V{i}->V{j}={adj[i][j]}")
    if row:
        print(f"  V{i}: {', '.join(row)}")
    else:
        print(f"  V{i}: (无出边)")

print()
print("=" * 60)
print("REASONING —— Dijkstra 逐轮执行")
print("=" * 60)

# 初始
print("\n初始:")
labels = [f"dist[V{i}]" for i in range(N)]
vals = [0 if i == 0 else INF for i in range(N)]
def fmt(x):
    return "∞" if x == INF else str(int(x))
print("  " + " | ".join(f"{labels[i]}={fmt(vals[i])}" for i in range(N)))

prev_snapshot = [-1] * N
for rnd_idx, (u, dist_snap) in enumerate(rounds):
    print(f"\n第{rnd_idx+1}轮：选入 V{u}（dist[V{u}]={fmt(dist[u])}）")
    print("  松弛后 dist:")
    print("  " + " | ".join(f"dist[V{i}]={fmt(dist_snap[i])}" for i in range(N)))
    print(f"  本轮 dist 快照: {dist_snap}")

print("\n松弛更新事件（dist 严格减小）:")
for (u, v, old, new) in relax_events:
    print(f"  V{u} 松弛 V{v}: dist[V{v}] {fmt(old)} -> {fmt(new)}, prev[V{v}]=V{u}")

print()
print("=" * 60)
print("ANSWER")
print("=" * 60)

print("\n【问题1】逐轮选入顶点与 dist 值:")
print(f"{'轮次':<6}{'选入':<6}" + "".join(f"dist[V{i}]  " for i in range(N)))
print(f"{'初始':<6}{'—':<6}" + "".join(f"{'∞' if i!=0 else '0':<10}" for i in range(N)))
for rnd_idx, (u, ds) in enumerate(rounds):
    print(f"{'第'+str(rnd_idx+1)+'轮':<6}{'V'+str(u):<6}" + "".join(f"{fmt(ds[i]):<10}" for i in range(N)))

print("\n【问题2】最短路径长度（V0 到各顶点）:")
for i in range(1, N):
    print(f"  dist[V{i}] = {fmt(dist[i])}")

print("\n【问题3】V0 到 V4 的完整最短路径:")
path = reconstruct_path(prev, 4)
path_str = " → ".join(f"V{x}" for x in path)
print(f"  路径序列: {path_str}")
print(f"  路径长度: {fmt(dist[4])}")
print(f"  前驱链:")
cur = 4
chain = []
while cur != -1:
    p = prev[cur]
    if p != -1:
        chain.append(f"prev[V{cur}]=V{p} (边V{p}->V{cur} 权值={adj[p][cur]})")
    cur = p
for c in chain:
    print(f"    {c}")

print("\n最终 dist 数组:", [fmt(d) for d in dist])
print("最终 prev 数组:", [f"V{p}" if p != -1 else "无" for p in prev])
print("收录顶点:", [f"V{i}" for i in range(N) if visited[i]])
print("未收录顶点:", [f"V{i}" for i in range(N) if not visited[i]])

# ===================== 通过条件 assert =====================
print()
print("=" * 60)
print("ASSERT —— 通过条件验证")
print("=" * 60)

# 条件1: 拓扑完整性 —— 恰好 5 轮收录（V0~V4 作为集合），V5 不被收录
assert len(rounds) == 5, f"条件1失败：收录轮数={len(rounds)}，期望5"
collected = [u for (u, _) in rounds]
assert sorted(collected) == [0, 1, 2, 3, 4], f"条件1失败：收录顶点集合={sorted(collected)}，期望{{V0,V1,V2,V3,V4}}"
assert collected[0] == 0, f"条件1失败：第1轮应选入源点V0"
assert not visited[5], "条件1失败：V5 不应被收录"
print(f"✓ 条件1（拓扑完整性）：恰好5轮收录，收录顺序={' → '.join(f'V{u}' for u in collected)}，V5不可达未被收录")

# 条件2: 不可达顶点 —— V5 的 dist 在所有轮次及最终保持 ∞
for rnd_idx, (u, ds) in enumerate(rounds):
    assert ds[5] == INF, f"条件2失败：第{rnd_idx+1}轮 dist[V5]={ds[5]}，应为∞"
assert dist[5] == INF, f"条件2失败：最终 dist[V5]={dist[5]}，应为∞"
print("✓ 条件2（不可达顶点）：V5 的 dist 在所有轮次及最终均为 ∞")

# 条件3: 松弛更新发生 —— 至少2个顶点（V1和V3）在第1轮之后被更短路径松弛
post_round1_relax_targets = set()
for rnd_idx, (u, _) in enumerate(rounds):
    if rnd_idx == 0:
        continue  # 跳过第1轮（V0 出边）
# 用 relax_events 判断：在第1轮之后发生的松弛
round_of = {}
for rnd_idx, (u, ds) in enumerate(rounds):
    round_of[u] = rnd_idx
post_relax = set()
for (u, v, old, new) in relax_events:
    if round_of[u] > 0:  # 非第1轮选入的顶点进行的松弛
        post_relax.add(v)
assert 1 in post_relax, f"条件3失败：V1 应在第1轮后被松弛"
assert 3 in post_relax, f"条件3失败：V3 应在第1轮后被松弛"
assert len(post_relax) >= 2, f"条件3失败：第1轮后被松弛的顶点数={len(post_relax)}，期望≥2"
print(f"✓ 条件3（松弛更新发生）：第1轮后被松弛的顶点 = {sorted(post_relax)}（含 V1 和 V3）")

# 条件4: 路径还原正确 —— V0到V4路径存在且唯一，长度=dist[4]，相邻顶点间有有向边
assert dist[4] != INF, "条件4失败：V4 不可达"
path4 = reconstruct_path(prev, 4)
assert path4[0] == 0, f"条件4失败：路径起点应为V0，实际{path4[0]}"
assert path4[-1] == 4, f"条件4失败：路径终点应为V4，实际{path4[-1]}"
path_len = 0
for i in range(len(path4) - 1):
    a, b = path4[i], path4[i + 1]
    assert adj[a][b] != INF, f"条件4失败：V{a}->V{b} 无有向边"
    path_len += adj[a][b]
assert path_len == dist[4], f"条件4失败：路径长度{path_len}≠dist[V4]={dist[4]}"
print(f"✓ 条件4（路径还原正确）：V0→V4 路径={' → '.join(f'V{x}' for x in path4)}，长度={int(dist[4])}，相邻顶点均有有向边")

# 条件5: 前驱链自洽 —— 沿 prev 链从 V4 回溯到 V0，路径长度之和 = dist[4]
cur = 4
chain_sum = 0
while prev[cur] != -1:
    p = prev[cur]
    assert adj[p][cur] != INF, f"条件5失败：V{p}->V{cur} 无有向边"
    chain_sum += adj[p][cur]
    cur = p
assert cur == 0, f"条件5失败：前驱链未回溯到V0，停在V{cur}"
assert chain_sum == dist[4], f"条件5失败：前驱链长度之和{chain_sum}≠dist[V4]={dist[4]}"
print(f"✓ 条件5（前驱链自洽）：V4 回溯到 V0，边权之和={int(chain_sum)}=dist[V4]={int(dist[4])}")

# 条件6: 选顶点无歧义 —— 每轮被选入顶点的 dist 在未收录顶点中唯一最小
for rnd_idx, (u, ds) in enumerate(rounds):
    min_val = ds[u]
    # 统计该轮选入时，未收录顶点中 dist==min_val 的数量
    # 需要重建该轮选入前的 visited 状态
    visited_before = [False] * N
    for k in range(rnd_idx):
        visited_before[rounds[k][0]] = True
    # 此时 u 的 dist 是 min_val，但 ds 是松弛后的快照
    # 选入时 u 的 dist = 松弛前的 dist，即上一轮结束的 dist
    if rnd_idx == 0:
        pre_dist = [0 if i == 0 else INF for i in range(N)]
    else:
        pre_dist = rounds[rnd_idx - 1][1][:]
    # u 是选入的，其 dist = pre_dist[u]
    candidates = [pre_dist[v] for v in range(N) if not visited_before[v]]
    min_d = min(candidates)
    count_min = sum(1 for v in range(N) if not visited_before[v] and pre_dist[v] == min_d)
    assert count_min == 1, f"条件6失败：第{rnd_idx+1}轮最小dist有{count_min}个并列"
    assert pre_dist[u] == min_d, f"条件6失败：第{rnd_idx+1}轮V{u}的dist{pre_dist[u]}≠最小值{min_d}"
print("✓ 条件6（选顶点无歧义）：每轮 dist 最小值在未收录顶点中唯一")

print()
print("=" * 60)
print("全部通过条件验证通过（6/6）")
print("=" * 60)
