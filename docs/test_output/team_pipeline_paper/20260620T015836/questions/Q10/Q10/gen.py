
# 快速排序前两趟划分结果 —— gen.py
题干翻译：Hoare 划分（挖坑法，先 high 后 low），前两趟 partition。


import copy

# ============================================================
# 数据
# ============================================================
INITIAL = [49, 38, 65, 97, 76, 13, 27, 30]

# ============================================================
# 标准 Hoare partition（挖坑法：先移动 high，再移动 low）
#   pivot = arr[lo]
#   先 high 向左找 < pivot → 填入坑
#   再 low  向右找 > pivot → 填入坑
#   返回 pivot 最终位置
# ============================================================
def partition_standard(arr, lo, hi):
    pivot = arr[lo]
    low, high = lo, hi
    while low < high:
        # 先移动 high（向左），找 < pivot
        while low < high and arr[high] >= pivot:
            high -= 1
        arr[low] = arr[high]
        # 再移动 low（向右），找 > pivot
        while low < high and arr[low] <= pivot:
            low += 1
        arr[high] = arr[low]
    arr[low] = pivot
    return low


# ============================================================
# 错误 C：先移动 low，再移动 high（方向反了）
# ============================================================
def partition_low_first(arr, lo, hi):
    pivot = arr[lo]
    low, high = lo, hi
    while low < high:
        # 先移动 low（向右），找 > pivot
        while low < high and arr[low] <= pivot:
            low += 1
        arr[high] = arr[low]
        # 再移动 high（向左），找 < pivot
        while low < high and arr[high] >= pivot:
            high -= 1
        arr[low] = arr[high]
    arr[low] = pivot
    return low


# ============================================================
# 错误 D：pivot 取末元素（而非首元素）
# ============================================================
def partition_last_pivot(arr, lo, hi):
    pivot = arr[hi]
    low, high = lo, hi
    while low < high:
        # 先移动 high（向左），找 < pivot
        while low < high and arr[high] >= pivot:
            high -= 1
        arr[low] = arr[high]
        # 再移动 low（向右），找 > pivot
        while low < high and arr[low] <= pivot:
            low += 1
        arr[high] = arr[low]
    arr[low] = pivot
    return low


# ============================================================
# 对 [lo,hi] 范围做一趟 partition，收集所有产生的 pivot 位置
# ============================================================
def do_one_pass(arr, lo, hi, partition_fn):
    """对单个区间做一次 partition，返回 pivot 最终位置。"""
    if lo >= hi:
        return lo
    return partition_fn(arr, lo, hi)


def do_two_passes(arr, partition_fn):
    """
    先在整个数组 [0, n-1] 上做第一趟 partition，
    再对第一趟划分产生的每个长度>=2 的子区间做第二趟 partition。
    返回 (最终数组, 第一趟后的pivot位置, 第二趟所有pivot位置列表)。
    """
    a = copy.deepcopy(arr)
    n = len(a)
    pivots_pass2 = []

    # 第一趟
    p1 = do_one_pass(a, 0, n - 1, partition_fn)

    # 第二趟：左侧子序列
    if p1 - 1 >= 1:  # 长度 >= 2
        p2l = do_one_pass(a, 0, p1 - 1, partition_fn)
        pivots_pass2.append((0, p1 - 1, p2l))

    # 第二趟：右侧子序列
    if n - 1 - (p1 + 1) >= 1:  # 长度 >= 2
        p2r = do_one_pass(a, p1 + 1, n - 1, partition_fn)
        pivots_pass2.append((p1 + 1, n - 1, p2r))

    return a, p1, pivots_pass2


def do_one_pass_only(arr, partition_fn):
    """仅做第一趟 partition。"""
    a = copy.deepcopy(arr)
    n = len(a)
    p1 = do_one_pass(a, 0, n - 1, partition_fn)
    return a, p1


# ============================================================
# 计算四个选项
# ============================================================

# A: 正确结果（标准 partition，前两趟）
arr_A, p1_A, p2_A = do_two_passes(INITIAL, partition_standard)

# B: 仅做第一趟
arr_B, p1_B = do_one_pass_only(INITIAL, partition_standard)

# C: 先移动 low（方向错误），前两趟
arr_C, p1_C, p2_C = do_two_passes(INITIAL, partition_low_first)

# D: pivot 取末元素，前两趟
arr_D, p1_D, p2_D = do_two_passes(INITIAL, partition_last_pivot)

A = tuple(arr_A)
B = tuple(arr_B)
C = tuple(arr_C)
D = tuple(arr_D)


# ============================================================
# 输出
# ============================================================
print("=== REASONING ===")
print(f"初始序列:          {INITIAL}")
print()
print(f"--- A (正确: 标准Hoare, 前2趟) ---")
print(f"  第一趟后: {arr_B}")  # arr_B 就是只做第一趟
print(f"  第一趟 pivot 位置: {p1_A}")
print(f"  第二趟后(A): {list(A)}")
print()
print(f"--- B (仅第一趟) ---")
print(f"  结果: {list(B)}")
print(f"  第一趟 pivot 位置: {p1_B}")
print()
print(f"--- C (先移动low, 前2趟) ---")
print(f"  结果: {list(C)}")
print()
print(f"--- D (末元素pivot, 前2趟) ---")
print(f"  结果: {list(D)}")
print()
print("=== ANSWER ===")
print(f"A = {list(A)}")
print(f"B = {list(B)}")
print(f"C = {list(C)}")
print(f"D = {list(D)}")
print()
print(f"PARAMS: {INITIAL}")
print()

# ============================================================
# assert 段 —— 打到通过条件
# ============================================================

# 条件1: 8 个互不相同的两位正整数
assert len(INITIAL) == 8, "序列长度必须为 8"
assert len(set(INITIAL)) == 8, "元素必须互不相同"
assert all(10 <= x <= 99 for x in INITIAL), "元素必须是两位正整数"
# 首元素 49 非最大非最小
assert INITIAL[0] != min(INITIAL), "首元素不能是最小值"
assert INITIAL[0] != max(INITIAL), "首元素不能是最大值"
# 第一趟后至少有一侧子序列长度 >= 2
assert (p1_A >= 2) or (len(INITIAL) - 1 - p1_A >= 2), \
    "第一趟后至少一侧子序列长度>=2，保证第二趟有实质内容"

# 条件2: 正确结果唯一确定 —— A 就是标准算法两趟后的结果（代码确定性产出）
# （由 partition_standard + do_two_passes 确定性保证）

# 条件3: 4 选项互异
assert len({A, B, C, D}) == 4, \
    f"4选项必须互异！A={A}, B={B}, C={C}, D={D}"

# 条件4: 干扰项对应声明错误类型
# B = 仅第一趟（第二趟未做 → B ≠ A）
assert B != A, "B(仅第一趟)必须不同于A(前两趟)"

# B 对应"漏做第二趟"：第一趟后只 partition 了 1 次，第二趟 0 次
assert p1_B == p1_A, "B的第一趟pivot位置应与A一致（同算法）"

# C = 先移动 low（方向错误）→ 应 ≠ A
assert C != A, "C(先移动low)必须不同于A(先移动high)"

# D = 末元素 pivot → 应 ≠ A
assert D != A, "D(末元素pivot)必须不同于A(首元素pivot)"

# 条件5: 干扰项合理性 —— 每个干扰项都是对 INITIAL 的排列（元素集合不变）
assert set(B) == set(INITIAL), "B 必须是初始序列的重排列"
assert set(C) == set(INITIAL), "C 必须是初始序列的重排列"
assert set(D) == set(INITIAL), "D 必须是初始序列的重排列"

print("=== ALL ASSERTS PASSED ===")
