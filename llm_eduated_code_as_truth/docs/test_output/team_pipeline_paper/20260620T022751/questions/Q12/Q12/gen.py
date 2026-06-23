def solve():
    # 图定义
    vertices = ['A', 'B', 'C', 'D', 'E', 'F']
    edges = [
        ('A', 'B', 4),
        ('A', 'C', 2),
        ('B', 'D', 3),
        ('B', 'E', 1),
        ('C', 'B', 1),
        ('C', 'D', 5),
        ('C', 'E', 8),
        ('D', 'E', 2),
        ('D', 'F', 6),
        ('E', 'F', 3),
    ]

    INF = float('inf')
    source = 'A'

    # 邻接表
    adj = {v: [] for v in vertices}
    for u, v, w in edges:
        adj[u].append((v, w))

    # 初始化
    dist = {v: INF for v in vertices}
    dist[source] = 0
    visited = set()
    parent = {v: None for v in vertices}

    # 记录每轮状态
    dist_history = []
    dist_history.append((0, None, dict(dist), set()))

    # 记录松弛更新次数
    update_count = {v: 0 for v in vertices}

    # Dijkstra 算法
    for round_num in range(1, len(vertices) + 1):
        # 选未访问顶点中 dist 最小者
        selected = None
        min_dist = INF
        for v in vertices:
            if v not in visited and dist[v] < min_dist:
                min_dist = dist[v]
                selected = v

        if selected is None:
            break

        visited.add(selected)

        # 松弛邻接边（仅对未访问顶点）
        for neighbor, weight in adj[selected]:
            if neighbor not in visited:
                if dist[selected] + weight < dist[neighbor]:
                    dist[neighbor] = dist[selected] + weight
                    parent[neighbor] = selected
                    update_count[neighbor] += 1

        dist_history.append((round_num, selected, dict(dist), set(visited)))

    # 输出
    print("PARAMS")
    print(f"顶点集: {vertices}")
    print(f"边集: {edges}")
    print(f"源点: {source}")

    print()
    print("REASONING")
    print("Dijkstra算法执行过程：")
    print(f"{'轮次':<6}{'选中':<6}{'A':<6}{'B':<6}{'C':<6}{'D':<6}{'E':<6}{'F':<6}{'visited'}")

    for round_num, selected, dist_snap, visited_snap in dist_history:
        dist_str = []
        for v in vertices:
            d = dist_snap[v]
            dist_str.append(str(d) if d != INF else '∞')
        visited_str = str(sorted(visited_snap))
        sel_str = selected if selected else '—'
        print(f"{round_num:<6}{sel_str:<6}{' '.join(dist_str)}  {visited_str}")

    print()
    print("最终最短路径：")
    for v in vertices:
        if v == source:
            print(f"A→{v}: 长度={dist[v]}, 路径={v}")
        else:
            path = []
            curr = v
            while curr is not None:
                path.append(curr)
                curr = parent[curr]
            path.reverse()
            print(f"A→{v}: 长度={dist[v]}, 路径={'→'.join(path)}")

    print()
    print("ANSWER")
    print(f"dist[A]={dist['A']}, dist[B]={dist['B']}, dist[C]={dist['C']}, dist[D]={dist['D']}, dist[E]={dist['E']}, dist[F]={dist['F']}")

    # ===== 验证段：通过条件 → assert =====
    print()
    print("VERIFICATION")

    # 条件1：连通性——源点到所有顶点可达
    for v in vertices:
        assert dist[v] < INF, f"顶点 {v} 不可达"
    print("✓ 条件1: 所有顶点从源点可达")

    # 条件2：存在松弛更新——至少一条边的松弛导致 dist 被更新
    total_updates = sum(update_count.values())
    assert total_updates >= 1, "没有发生任何松弛更新"
    print(f"✓ 条件2: 存在松弛更新（共{total_updates}次）")

    # 条件3：存在"已确定不更新"陷阱
    # 存在边(x,y)，y在x之前被visited，且 dist[x]+w(x,y) > dist[y]
    visit_order = {}
    for round_num, selected, _, _ in dist_history:
        if selected is not None:
            visit_order[selected] = round_num

    trap_found = False
    for u, v, w in edges:
        if v in visit_order and u in visit_order:
            if visit_order[v] < visit_order[u]:  # v 在 u 之前被访问
                if dist[u] + w > dist[v]:
                    trap_found = True
                    print(f"✓ 条件3: 边 {u}→{v} 的松弛不更新（{v}在{u}之前被访问，dist[{u}]+{w}={dist[u]+w} > dist[{v}]={dist[v]}）")
                    break

    assert trap_found, "未找到'已确定不更新'陷阱"

    # 条件4：三角不等式——对所有边(u,v)，dist[v] <= dist[u] + w(u,v)
    for u, v, w in edges:
        assert dist[v] <= dist[u] + w, f"三角不等式不满足: 边 {u}→{v}, dist[{v}]={dist[v]} > dist[{u}]+{w}={dist[u]+w}"
    print("✓ 条件4: 三角不等式满足")

    # 条件5：最短路径一致性——每个非源点v，dist[v] = dist[p[v]] + w(p[v],v)
    for v in vertices:
        if v == source:
            continue
        p = parent[v]
        assert p is not None, f"顶点 {v} 无父节点"
        w_pv = None
        for u, vv, ww in edges:
            if u == p and vv == v:
                w_pv = ww
                break
        assert w_pv is not None, f"边 {p}→{v} 不存在"
        assert dist[v] == dist[p] + w_pv, f"路径不一致: dist[{v}]={dist[v]} != dist[{p}]+w={dist[p]+w_pv}"
    print("✓ 条件5: 最短路径一致性满足")

    return dist, parent


solve()
