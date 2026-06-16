"""
银行家算法题目参数生成器
生成：进程数、资源类型、Max/Allocation/Need矩阵、Available向量
校验：Need>=0, 资源总量一致, 存在安全序列
"""

def generate_banker_params():
    # 5个进程 P0-P4，3类资源 A/B/C
    n_processes = 5
    n_resources = 3
    resource_names = ['A', 'B', 'C']
    
    # 资源总量
    total = [10, 5, 7]
    
    # Allocation 矩阵 (硬编码一组已知安全的配置)
    allocation = [
        [0, 1, 0],  # P0
        [2, 0, 0],  # P1
        [3, 0, 2],  # P2
        [2, 1, 1],  # P3
        [0, 0, 2],  # P4
    ]
    
    # Max 矩阵
    max_matrix = [
        [7, 5, 3],  # P0
        [3, 2, 2],  # P1
        [9, 0, 2],  # P2
        [2, 2, 2],  # P3
        [4, 3, 3],  # P4
    ]
    
    # 计算 Need = Max - Allocation
    need = []
    for i in range(n_processes):
        row = []
        for j in range(n_resources):
            val = max_matrix[i][j] - allocation[i][j]
            if val < 0:
                print(f"ERROR: Need[{i}][{j}] = {val} < 0, Max < Allocation")
                return None
            row.append(val)
        need.append(row)
    
    # 计算 Available = Total - sum(Allocation)
    allocated_sum = [0] * n_resources
    for i in range(n_processes):
        for j in range(n_resources):
            allocated_sum[j] += allocation[i][j]
    
    available = [total[j] - allocated_sum[j] for j in range(n_resources)]
    
    # 校验 Available >= 0
    for j in range(n_resources):
        if available[j] < 0:
            print(f"ERROR: Available[{j}] = {available[j]} < 0, 资源超分配")
            return None
    
    # 校验安全序列是否存在
    safe_seq = find_safe_sequence(n_processes, n_resources, available[:], allocation, need)
    if safe_seq is None:
        print("ERROR: 不存在安全序列，初始状态不安全")
        return None
    
    # 打印结果
    print("=" * 60)
    print("银行家算法参数生成成功")
    print("=" * 60)
    print(f"进程数: {n_processes} (P0-P4)")
    print(f"资源类型: {n_resources} (A, B, C)")
    print(f"资源总量: A={total[0]}, B={total[1]}, C={total[2]}")
    print()
    print("Allocation 矩阵:")
    print(f"{'':>4} {'A':>4} {'B':>4} {'C':>4}")
    for i in range(n_processes):
        print(f"P{i}: {allocation[i][0]:>4} {allocation[i][1]:>4} {allocation[i][2]:>4}")
    print()
    print("Max 矩阵:")
    print(f"{'':>4} {'A':>4} {'B':>4} {'C':>4}")
    for i in range(n_processes):
        print(f"P{i}: {max_matrix[i][0]:>4} {max_matrix[i][1]:>4} {max_matrix[i][2]:>4}")
    print()
    print("Need 矩阵:")
    print(f"{'':>4} {'A':>4} {'B':>4} {'C':>4}")
    for i in range(n_processes):
        print(f"P{i}: {need[i][0]:>4} {need[i][1]:>4} {need[i][2]:>4}")
    print()
    print(f"Available: A={available[0]}, B={available[1]}, C={available[2]}")
    print()
    print(f"安全序列: {' -> '.join(['P' + str(p) for p in safe_seq])}")
    print("=" * 60)
    
    return {
        'n_processes': n_processes,
        'n_resources': n_resources,
        'resource_names': resource_names,
        'total': total,
        'allocation': allocation,
        'max_matrix': max_matrix,
        'need': need,
        'available': available,
        'safe_seq': safe_seq
    }


def find_safe_sequence(n, m, available, allocation, need):
    """安全算法：寻找安全序列"""
    work = available[:]
    finish = [False] * n
    safe_seq = []
    
    while len(safe_seq) < n:
        found = False
        for i in range(n):
            if finish[i]:
                continue
            # 检查 Need[i] <= Work
            can_allocate = True
            for j in range(m):
                if need[i][j] > work[j]:
                    can_allocate = False
                    break
            if can_allocate:
                # 模拟分配
                for j in range(m):
                    work[j] += allocation[i][j]
                finish[i] = True
                safe_seq.append(i)
                found = True
                break  # 重新开始扫描
        if not found:
            return None  # 不安全
    
    return safe_seq


if __name__ == '__main__':
    result = generate_banker_params()
    if result is None:
        print("参数生成失败")
        exit(1)
