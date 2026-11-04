"""Dijkstra 算法 dist 数组更新过程 - 建模代码"""

import heapq

def dijkstra_trace(vertices, edges, source):
    """
    模拟 Dijkstra 算法执行过程，追踪 dist 数组的逐轮更新。
    
    返回:
        final_dist: 最终 dist 数组
        update_counts: 每个顶点的更新次数（初始赋值不计）
        round_states: 每轮迭代后的 (加入S的顶点, dist数组快照)
    """
    n = len(vertices)
    adj = {v: [] for v in vertices}
    for u, v, w in edges:
        adj[u].append((v, w))
    
    INF = float('inf')
    dist = {v: INF for v in vertices}
    dist[source] = 0
    S = set()
    
    # 记录每个顶点的更新次数（初始赋值不计）
    update_counts = {v: 0 for v in vertices}
    # 记录每轮状态
    round_states = []
    
    # 优先队列: (dist, vertex)
    pq = [(0, source)]
    
    while pq:
        d, u = heapq.heappop(pq)
        
        # 如果已经确定最短路径，跳过
        if u in S:
            continue
        
        # 将 u 加入 S
        S.add(u)
        round_num = len(S)
        
        # 记录本轮状态（加入S之后，松弛之前）
        dist_snapshot = dict(dist)
        round_states.append((round_num, u, dist_snapshot))
        
        # 松弛操作
        for v, w in adj[u]:
            if v not in S and dist[u] + w < dist[v]:
                old_dist = dist[v]
                dist[v] = dist[u] + w
                update_counts[v] += 1
                heapq.heappush(pq, (dist[v], v))
    
    return dist, update_counts, round_states


def main():
    # 图的定义
    vertices = ['v1', 'v2', 'v3', 'v4', 'v5']
    edges = [
        ('v1', 'v2', 4),
        ('v1', 'v3', 2),
        ('v2', 'v4', 3),
        ('v2', 'v5', 7),
        ('v3', 'v2', 1),
        ('v3', 'v4', 5),
        ('v3', 'v5', 10),
        ('v4', 'v5', 3),
    ]
    source = 'v1'
    
    final_dist, update_counts, round_states = dijkstra_trace(vertices, edges, source)
    
    # ========== PARAMS ==========
    print("=== PARAMS ===")
    print(f"顶点: {vertices}")
    print(f"边集: {edges}")
    print(f"源点: {source}")
    
    # ========== REASONING ==========
    print("\n=== REASONING ===")
    print("Dijkstra 算法逐轮执行过程:")
    for round_num, added_vertex, dist_state in round_states:
        dist_str = ", ".join(f"{v}={dist_state[v] if dist_state[v] != float('inf') else '∞'}" for v in vertices)
        print(f"  第{round_num}轮: 加入S的顶点={added_vertex}, dist=[{dist_str}]")
    
    print(f"\n各顶点更新次数: {update_counts}")
    
    # 子问(1): 最终 dist 数组
    print(f"\n子问(1) 最终dist: v1={final_dist['v1']}, v2={final_dist['v2']}, v3={final_dist['v3']}, v4={final_dist['v4']}, v5={final_dist['v5']}")
    
    # 子问(2): v2 更新次数
    print(f"子问(2) v2更新次数: {update_counts['v2']}")
    
    # 子问(3): v5 更新次数
    print(f"子问(3) v5更新次数: {update_counts['v5']}")
    
    # 子问(4): 第3轮状态
    round3 = [rs for rs in round_states if rs[0] == 3][0]
    _, added_v3, dist3 = round3
    dist3_str = ", ".join(f"dist[{v}]={dist3[v] if dist3[v] != float('inf') else '∞'}" for v in vertices)
    print(f"子问(4) 第3轮加入S的顶点: {added_v3}, 此时{dist3_str}")
    
    # ========== ANSWER ==========
    print("\n=== ANSWER ===")
    print(f"(1) dist[v1]={final_dist['v1']}, dist[v2]={final_dist['v2']}, dist[v3]={final_dist['v3']}, dist[v4]={final_dist['v4']}, dist[v5]={final_dist['v5']}")
    print(f"(2) dist[v2] 更新次数: {update_counts['v2']}")
    print(f"(3) dist[v5] 更新次数: {update_counts['v5']}")
    print(f"(4) 第3轮加入S的顶点: {added_v3}, dist状态: {dist3_str}")
    
    # ========== 验证段：通过条件翻译为 assert ==========
    print("\n=== 验证通过条件 ===")
    
    # 条件1: 非平凡性 - 至少存在一个顶点 v≠v1，其 dist[v] 被更新 ≥1 次
    non_source_updates = {v: c for v, c in update_counts.items() if v != source}
    assert any(c >= 1 for c in non_source_updates.values()), \
        f"条件1失败: 非源点更新次数={non_source_updates}，应至少有一个≥1"
    print("✓ 条件1(非平凡性): 存在非源点被更新≥1次")
    
    # 条件2: 多轮更新 - 至少存在一个顶点，其 dist 值被更新 ≥2 次
    assert any(c >= 2 for c in update_counts.values()), \
        f"条件2失败: 所有顶点更新次数={update_counts}，应至少有一个≥2"
    print("✓ 条件2(多轮更新): 存在顶点被更新≥2次")
    
    # 条件3: 过程可追踪 - 第3轮迭代时，dist数组状态与最终状态不同
    round3_dist = dist3
    final_dist_check = final_dist
    assert round3_dist != final_dist_check, \
        f"条件3失败: 第3轮dist={round3_dist} 与最终dist={final_dist_check} 相同，应不同"
    print("✓ 条件3(过程可追踪): 第3轮dist状态与最终状态不同")
    
    print("\n所有通过条件验证通过！")


if __name__ == "__main__":
    main()
