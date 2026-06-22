# ===== Banker's Algorithm — Complete Solution =====

# ===== 题目参数定义 =====
Total = [10, 6, 8]  # 资源总数量 A, B, C

Maximum = [
    [8, 5, 4],  # P0
    [3, 2, 2],  # P1
    [9, 0, 3],  # P2
    [2, 2, 2],  # P3
    [4, 3, 3],  # P4
]

Allocation = [
    [1, 1, 0],  # P0
    [2, 0, 0],  # P1
    [3, 0, 2],  # P2
    [1, 1, 1],  # P3
    [0, 0, 2],  # P4
]

# ===== 子问题(1): Need 矩阵和 Available 向量 =====
Need = []
for i in range(5):
    Need.append([Maximum[i][j] - Allocation[i][j] for j in range(3)])

print("===== 子问题(1): Need 矩阵 =====")
for i in range(5):
    print(f"  P{i}: {Need[i]}")

sum_alloc = [sum(Allocation[i][j] for i in range(5)) for j in range(3)]
Available = [Total[j] - sum_alloc[j] for j in range(3)]
print(f"\n===== 子问题(1): Available 向量 =====")
print(f"  Sum(Allocation) = {sum_alloc}")
print(f"  Available = Total - Sum(Allocation) = {Total} - {sum_alloc} = {Available}")

# ===== 子问题(2): 安全性算法 =====
print("\n===== 子问题(2): 安全性算法 =====")

Work = Available[:]
Finish = [False] * 5
safe_sequence = []
print(f"  初始: Work = {Work}")

found_any = True
iteration = 0
while found_any:
    found_any = False
    iteration += 1
    for i in range(5):
        if not Finish[i]:
            can_finish = all(Need[i][j] <= Work[j] for j in range(3))
            if can_finish:
                print(f"  第{iteration}轮: P{i} 可完成 (Need={Need[i]} <= Work={Work})")
                Work = [Work[j] + Allocation[i][j] for j in range(3)]
                print(f"    Work 更新: +Allocation[P{i}]={Allocation[i]} -> Work={Work}")
                Finish[i] = True
                safe_sequence.append(i)
                found_any = True

is_safe = all(Finish)
seq_str = " -> ".join(f"P{p}" for p in safe_sequence)
print(f"\n  安全序列: {seq_str}")
print(f"  最终 Work = {Work}")
print(f"  系统状态: {'安全 (SAFE)' if is_safe else '不安全 (UNSAFE)'}")

# ===== 子问题(3): P0 请求 Request0 = (3, 4, 3) =====
print("\n===== 子问题(3): P0 请求 Request0 = (3, 4, 3) =====")

Request0 = [3, 4, 3]

# 步骤1: Request <= Need[P0]
step1 = all(Request0[j] <= Need[0][j] for j in range(3))
print(f"\n  步骤1: Request <= Need[P0]?")
print(f"    Request = {Request0}, Need[P0] = {Need[0]}")
print(f"    结果: {'通过' if step1 else '失败'}")

# 步骤2: Request <= Available
step2 = all(Request0[j] <= Available[j] for j in range(3))
print(f"\n  步骤2: Request <= Available?")
print(f"    Request = {Request0}, Available = {Available}")
print(f"    结果: {'通过' if step2 else '失败'}")

# 步骤3: 假装分配 + 安全性检查
if step1 and step2:
    print(f"\n  步骤3: 假装分配后进行安全性检查")
    Available_new = [Available[j] - Request0[j] for j in range(3)]
    Allocation_new = [row[:] for row in Allocation]
    Need_new = [row[:] for row in Need]
    for j in range(3):
        Allocation_new[0][j] += Request0[j]
        Need_new[0][j] -= Request0[j]

    print(f"    新 Available = {Available_new}")
    print(f"    新 Allocation[P0] = {Allocation_new[0]}")
    print(f"    新 Need[P0] = {Need_new[0]}")
    print(f"\n    更新后的状态:")
    for i in range(5):
        print(f"      P{i}: Allocation={Allocation_new[i]}, Need={Need_new[i]}")

    Work2 = Available_new[:]
    Finish2 = [False] * 5
    safe_seq2 = []
    print(f"\n    安全性算法: 初始 Work = {Work2}")

    found = True
    while found:
        found = False
        for i in range(5):
            if not Finish2[i]:
                can = all(Need_new[i][j] <= Work2[j] for j in range(3))
                if can:
                    print(f"      P{i}: Need={Need_new[i]} <= Work={Work2} -> 可完成")
                    Work2 = [Work2[j] + Allocation_new[i][j] for j in range(3)]
                    Finish2[i] = True
                    safe_seq2.append(i)
                    found = True

    if not safe_seq2:
        print(f"    无任何进程可完成 (Work = {Available_new}, 所有 Need 均大于 Work):")
        for i in range(5):
            print(f"      P{i}: Need={Need_new[i]}")

    is_safe2 = all(Finish2)
    print(f"\n    安全性检查结果: {'安全' if is_safe2 else '不安全'}")
    print(f"    结论: {'可以批准请求' if is_safe2 else '不能批准请求，P0 须等待'}")

    # 资源守恒验证
    sum_alloc_new = [sum(Allocation_new[i][j] for i in range(5)) for j in range(3)]
    total_check = [sum_alloc_new[j] + Available_new[j] for j in range(3)]
    print(f"\n    资源守恒: Sum(Alloc)+Avail = {sum_alloc_new}+{Available_new} = {total_check} (Total={Total})")

# ===== 最终输出 =====
print(f"\n{'='*60}")
print(f"ANSWER:")
print(f"  (1) Need矩阵见上方; Available = {Available}")
print(f"  (2) 系统处于安全状态, 安全序列: {seq_str}")
print(f"  (3) Request0=(3,4,3) 不能批准 (通过前两步但第三步安全性检查不通过)")
