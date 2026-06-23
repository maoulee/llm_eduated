# -*- coding: utf-8 -*-
"""
银行家算法综合题生成器
- 5 进程, 3 资源
- 设问1: P1 请求资源, 能否分配? 安全序列?
- 设问2: 在(1)之后 P4 请求资源, 能否分配? 为什么?
- 设问3: 概念辨析 - 安全状态与死锁状态的关系
"""
import itertools

# ============================================================
# 数据定义
# ============================================================
R = 3  # 资源种类数
N = 5  # 进程数
NAME = ['A', 'B', 'C']

# 当前可用资源
Available = [3, 3, 2]

# 最大需求矩阵 Max[进程][资源]
Max = [
    [5, 5, 5],   # P0
    [3, 2, 2],   # P1
    [4, 0, 2],   # P2
    [2, 2, 2],   # P3
    [4, 3, 3],   # P4
]

# 已分配矩阵 Allocation[进程][资源]
Allocation = [
    [2, 1, 2],   # P0
    [1, 0, 0],   # P1
    [2, 0, 2],   # P2
    [2, 1, 1],   # P3
    [0, 0, 2],   # P4
]

def calc_need(max_m, alloc):
    return [[max_m[i][j] - alloc[i][j] for j in range(R)] for i in range(N)]

def vec_le(a, b):
    """a <= b (逐分量)"""
    return all(a[i] <= b[i] for i in range(len(a)))

def vec_add(a, b):
    return [a[i] + b[i] for i in range(len(a))]

def vec_sub(a, b):
    return [a[i] - b[i] for i in range(len(a))]

def safety_check(available, max_m, alloc):
    """
    安全性算法
    返回 (is_safe, safe_sequences_list)
    safe_sequences_list: 所有安全序列的列表
    """
    need = calc_need(max_m, alloc)
    work = list(available)
    finish = [False] * N
    sequences = []

    def backtrack(work, finish, path):
        done = True
        for i in range(N):
            if not finish[i] and vec_le(need[i], work):
                done = False
                new_work = vec_add(work, alloc[i])
                new_finish = finish[:]
                new_finish[i] = True
                backtrack(new_work, new_finish, path + [i])
        if done and all(finish):
            sequences.append(path[:])

    backtrack(work, finish, [])

    is_safe = len(sequences) > 0
    return is_safe, sequences

def print_matrix(label, mat, row_names=None):
    print(f"{label}")
    if row_names is None:
        row_names = [f"P{i}" for i in range(N)]
    header = f"{'进程':>6}  " + "  ".join(f"{NAME[j]:>4}" for j in range(R))
    print(header)
    for i in range(len(mat)):
        row = f"{row_names[i]:>6}  " + "  ".join(f"{mat[i][j]:>4}" for j in range(R))
        print(row)

def fmt_vec(v):
    return "(" + ", ".join(str(x) for x in v) + ")"

# ============================================================
# 计算 Need
# ============================================================
Need = calc_need(Max, Allocation)

# ============================================================
# 初始状态安全性检查
# ============================================================
init_safe, init_seqs = safety_check(Available, Max, Allocation)

# ============================================================
# 设问1: P1 请求 Request1 = (1, 0, 2)
# ============================================================
req1 = [1, 0, 2]
P1 = 1

# 步骤1: Request <= Need[P1]?
check1a = vec_le(req1, Need[P1])
# 步骤2: Request <= Available?
check1b = vec_le(req1, Available)
# 步骤3: 试探性分配后安全性检查
avail_after1 = vec_sub(Available, req1)
alloc_after1 = [row[:] for row in Allocation]
for j in range(R):
    alloc_after1[P1][j] += req1[j]
max_after1 = [row[:] for row in Max]

safe1, seqs1 = safety_check(avail_after1, max_after1, alloc_after1)

# ============================================================
# 设问2: 在(1)之后, P4 请求 Request2 = (3, 3, 0)
# ============================================================
req2 = [3, 3, 0]
P4 = 4

# 基于设问1已分配后的状态
need_after1 = calc_need(max_after1, alloc_after1)
check2a = vec_le(req2, need_after1[P4])
check2b = vec_le(req2, avail_after1)

# 如果通过前两步检查, 再做安全性检查
if check2a and check2b:
    avail_after2 = vec_sub(avail_after1, req2)
    alloc_after2 = [row[:] for row in alloc_after1]
    for j in range(R):
        alloc_after2[P4][j] += req2[j]
    safe2, seqs2 = safety_check(avail_after2, max_after1, alloc_after2)
else:
    avail_after2 = None
    safe2 = False
    seqs2 = []

# ============================================================
# 设问3: 安全状态与死锁状态的关系 (概念题)
# ============================================================
# 答案: 安全状态一定不会死锁; 不安全状态不一定会死锁, 但有可能死锁。
# 系统处于安全状态时, 一定可以找到一个安全序列使所有进程顺利完成。
# 处于不安全状态时, 不一定发生死锁, 因为进程可能释放资源而不按最大需求申请。

# ============================================================
# 输出 4 段
# ============================================================
print("===== 参数 =====")
print()
print(f"资源种类: {R} (A, B, C)")
print(f"进程数量: {N} (P0~P4)")
print()
print_matrix("最大需求矩阵 Max:", Max)
print()
print_matrix("已分配矩阵 Allocation:", Allocation)
print()
print_matrix("需求矩阵 Need (Need = Max - Allocation):", Need)
print()
print(f"当前可用资源 Available = {fmt_vec(Available)}")
print()

print(f"初始状态安全性: {'安全' if init_safe else '不安全'}")
if init_seqs:
    # 只显示前 3 个安全序列
    shown = init_seqs[:3]
    for s in shown:
        names = [f"P{i}" for i in s]
        print(f"  安全序列: {' → '.join(names)}")
    if len(init_seqs) > 3:
        print(f"  ... 共 {len(init_seqs)} 个安全序列")

print()
print(f"设问1: P1 请求 Request1 = {fmt_vec(req1)}")
print(f"  步骤1 Request1 ≤ Need[P1]? {fmt_vec(req1)} ≤ {fmt_vec(Need[P1])} → {'是' if check1a else '否'}")
print(f"  步骤2 Request1 ≤ Available? {fmt_vec(req1)} ≤ {fmt_vec(Available)} → {'是' if check1b else '否'}")
print(f"  步骤3 试探分配后安全性: {'安全' if safe1 else '不安全'}")
if safe1:
    print(f"  分配后 Available = {fmt_vec(avail_after1)}")
    for s in seqs1[:3]:
        names = [f"P{i}" for i in s]
        print(f"  安全序列: {' → '.join(names)}")
    if len(seqs1) > 3:
        print(f"  ... 共 {len(seqs1)} 个安全序列")
print(f"  结论: {'可以分配' if safe1 else '不可以分配'}")
print()

print(f"设问2: P4 请求 Request2 = {fmt_vec(req2)}")
print(f"  (基于设问1已分配后的状态)")
print(f"  Need[P4] after (1) = {fmt_vec(need_after1[P4])}")
print(f"  Available after (1) = {fmt_vec(avail_after1)}")
print(f"  步骤1 Request2 ≤ Need[P4]? {fmt_vec(req2)} ≤ {fmt_vec(need_after1[P4])} → {'是' if check2a else '否'}")
print(f"  步骤2 Request2 ≤ Available? {fmt_vec(req2)} ≤ {fmt_vec(avail_after1)} → {'是' if check2b else '否'}")
if check2a and check2b:
    print(f"  步骤3 试探分配后安全性: {'安全' if safe2 else '不安全'}")
print(f"  结论: {'可以分配' if (check2a and check2b and safe2) else '不可以分配'}")
if not check2a:
    print(f"  原因: 请求超过最大声明需求")
elif not check2b:
    print(f"  原因: 请求超过当前可用资源")
elif not safe2:
    print(f"  原因: 分配后系统进入不安全状态")
print()

print("===== 题干描述 =====")
print()
print("某系统中有 5 个进程 P0~P4 和 3 类资源 A、B、C，系统采用银行家算法进行死锁避免。")
print("当前时刻系统的资源分配状态如下表所示：")
print()
print("| 进程 | Max(A,B,C) | Allocation(A,B,C) |")
print("|------|------------|-------------------|")
for i in range(N):
    print(f"| P{i}   | ({Max[i][0]}, {Max[i][1]}, {Max[i][2]})       | ({Allocation[i][0]}, {Allocation[i][1]}, {Allocation[i][2]})              |")
print()
print(f"当前可用资源向量 Available = {fmt_vec(Available)}。")
print()
print("请回答以下问题：")
print()
print(f"（1）进程 P1 发出资源请求 Request1 = {fmt_vec(req1)}，系统是否可以满足该请求？")
print(f"    若可以，请给出一个安全序列；若不可以，请说明理由。")
print()
print(f"（2）在问题（1）的请求被满足后，进程 P4 发出资源请求 Request2 = {fmt_vec(req2)}，")
print(f"    系统是否可以满足该请求？请说明理由。")
print()
print("（3）有人说\u201c系统处于不安全状态就一定会发生死锁\u201d，这种说法是否正确？请简述理由。")
print()

print("===== 求解路径 =====")
print()
print("【问题1】P1 请求 Request1 =", fmt_vec(req1))
print()
print("Step 1: 检查 Request1 ≤ Need[P1]")
print(f"  Need[P1] = Max[P1] - Allocation[P1] = {fmt_vec(Max[P1])} - {fmt_vec(Allocation[P1])} = {fmt_vec(Need[P1])}")
print(f"  {fmt_vec(req1)} ≤ {fmt_vec(Need[P1])} ? {'满足' if check1a else '不满足'}")
print()
print("Step 2: 检查 Request1 ≤ Available")
print(f"  {fmt_vec(req1)} ≤ {fmt_vec(Available)} ? {'满足' if check1b else '不满足'}")
print()
print("Step 3: 试探性分配，进行安全性检查")
print(f"  Available' = Available - Request1 = {fmt_vec(Available)} - {fmt_vec(req1)} = {fmt_vec(avail_after1)}")
print(f"  Allocation'[P1] = {fmt_vec(Allocation[P1])} + {fmt_vec(req1)} = {fmt_vec(alloc_after1[P1])}")
print(f"  Need'[P1] = {fmt_vec(Need[P1])} - {fmt_vec(req1)} = {fmt_vec([Need[P1][j]-req1[j] for j in range(R)])}")
print()
print("  安全性检查过程（Work = Available'）:")
print()

# 手动模拟安全性算法过程
need1_after = calc_need(max_after1, alloc_after1)
work = list(avail_after1)
finish = [False] * N
step_count = 0
safe_path = []
for _ in range(N):
    for i in range(N):
        if not finish[i] and vec_le(need1_after[i], work):
            step_count += 1
            safe_path.append(i)
            print(f"  第{step_count}步: Need'[P{i}] = {fmt_vec(need1_after[i])} ≤ Work = {fmt_vec(work)} ✓")
            work = vec_add(work, alloc_after1[i])
            finish[i] = True
            print(f"         分配后 Work = {fmt_vec(work)}")

print()
if safe1:
    names = [f"P{i}" for i in safe_path]
    print(f"  所有进程均能完成，系统安全！")
    print(f"  安全序列: {' → '.join(names)}")
print()
print(f"  结论: {'可以满足 P1 的请求' if safe1 else '不可以满足 P1 的请求'}")
print()

print("【问题2】P4 请求 Request2 =", fmt_vec(req2))
print()
print(f"  基于问题（1）已分配后的状态：")
print(f"  Available = {fmt_vec(avail_after1)}")
print(f"  Need[P4] = {fmt_vec(need_after1[P4])}")
print()
print("Step 1: 检查 Request2 ≤ Need[P4]")
print(f"  {fmt_vec(req2)} ≤ {fmt_vec(need_after1[P4])} ? {'满足' if check2a else '不满足'}")
print()
print("Step 2: 检查 Request2 ≤ Available")
print(f"  {fmt_vec(req2)} ≤ {fmt_vec(avail_after1)} ? {'满足' if check2b else '不满足'}")
print()
if not check2b:
    print(f"  由于 Request2 中 A 的需求({req2[0]}) > Available 中 A 的数量({avail_after1[0]})，")
    print(f"  系统当前没有足够的资源满足 P4 的请求。")
    print(f"  根据 P4 已等待资源不足的情况，P4 必须阻塞等待。")
    print()
    print(f"  结论: 不可以满足 P4 的请求。原因：请求的资源数超过了系统当前可用资源数。")
elif not check2a:
    print(f"  请求超过 P4 声明的最大需求，不允许。")
    print(f"  结论: 不可以满足 P4 的请求。原因：请求超过最大声明需求。")
else:
    print(f"  Step 3: 试探性分配后安全性检查: {'安全' if safe2 else '不安全'}")
    if not safe2:
        print(f"  结论: 不可以满足 P4 的请求。原因：分配后系统进入不安全状态。")
    else:
        print(f"  结论: 可以满足 P4 的请求。")
print()

print("【问题3】安全状态与死锁状态的关系")
print()
print("  该说法不正确。")
print()
print("  安全状态和不安全状态的定义：")
print("  - 安全状态：系统能按某种顺序（安全序列）为每个进程分配所需资源，")
print("    使每个进程都能顺利完成。")
print("  - 不安全状态：不存在这样的安全序列。")
print()
print("  关键区别：")
print("  - 安全状态 → 一定不会发生死锁。")
print("  - 不安全状态 → 不一定会发生死锁。")
print("    因为不安全状态只是说\u201c无法保证所有进程都能完成\u201d，")
print("    但实际运行中，进程可能不需要申请其声明的最大资源就能完成执行并释放资源，")
print("    从而使系统脱离潜在死锁。死锁只是不安全状态的一种可能结果，而非必然结果。")
print()

print("===== 答案 =====")
print()
if safe1:
    names1 = [f"P{i}" for i in seqs1[0]]
    ans1 = f"可以满足。安全序列之一：{' → '.join(names1)}"
else:
    ans1 = "不可以满足。"
print(f"（1）{ans1}")
print()
if check2a and check2b and safe2:
    ans2 = "可以满足。"
elif not check2a:
    ans2 = "不可以满足。原因：请求超过最大声明需求。"
elif not check2b:
    ans2 = "不可以满足。原因：请求的资源数超过系统当前可用资源数，P4 必须阻塞等待。"
else:
    ans2 = "不可以满足。原因：分配后系统进入不安全状态。"
print(f"（2）{ans2}")
print()
print("（3）不正确。安全状态一定不会死锁，但不安全状态不一定会死锁。")
print("    不安全状态只是不存在安全序列，进程实际执行时可能不按最大需求申请资源，")
print("    从而避免死锁。死锁是不安全状态的可能结果，而非必然结果。")
