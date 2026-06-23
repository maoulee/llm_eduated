"""
快速排序前两趟 partition 模拟
序列: [12, 5, 18, 3, 9, 7, 15, 2, 10, 4]
"""

SEQ = [12, 5, 18, 3, 9, 7, 15, 2, 10, 4]

# ============================================================
# 正确实现：标准双指针 Hoare partition（先 i 后 j，基准与 a[j] 交换）
# ============================================================
def hoare_partition(arr, low, high):
    """标准双指针 partition，返回 pivot 最终位置"""
    pivot = arr[low]
    i = low + 1
    j = high
    while True:
        while i <= j and arr[i] <= pivot:
            i += 1
        while i <= j and arr[j] >= pivot:
            j -= 1
        if i < j:
            arr[i], arr[j] = arr[j], arr[i]
        else:
            break
    arr[low], arr[j] = arr[j], arr[low]
    return j

def two_passes(seq, **kwargs):
    """执行前两趟 partition，返回 (结果序列, 第一趟pivot位置, 第二趟pivot位置)"""
    a = list(seq)
    p1 = hoare_partition(a, 0, len(a) - 1)
    # 第二趟对左侧子序列
    p2 = hoare_partition(a, 0, p1 - 1) if p1 > 0 else -1
    return a, p1, p2

# ============================================================
# 干扰项 B：第一趟基准归位错误（与 a[i] 而非 a[j] 交换）
# ============================================================
def hoare_partition_swap_i(arr, low, high):
    """错误：基准与 a[i] 交换而非 a[j]"""
    pivot = arr[low]
    i = low + 1
    j = high
    while True:
        while i <= j and arr[i] <= pivot:
            i += 1
        while i <= j and arr[j] >= pivot:
            j -= 1
        if i < j:
            arr[i], arr[j] = arr[j], arr[i]
        else:
            break
    # 错误：与 a[i] 交换
    arr[low], arr[i] = arr[i], arr[low]
    return i

def two_passes_swap_i(seq):
    a = list(seq)
    p1 = hoare_partition_swap_i(a, 0, len(a) - 1)
    p2 = hoare_partition(a, 0, p1 - 1) if p1 > 0 else -1
    return a, p1, p2

# ============================================================
# 干扰项 C：Lomuto 单指针分区方案（而非双指针 Hoare 方案）
# ============================================================
def lomuto_partition(arr, low, high):
    """Lomuto 单指针分区方案"""
    pivot = arr[high]  # Lomuto 通常取最后一个元素作为 pivot
    store_index = low
    for k in range(low, high):
        if arr[k] < pivot:
            arr[store_index], arr[k] = arr[k], arr[store_index]
            store_index += 1
    arr[store_index], arr[high] = arr[high], arr[store_index]
    return store_index

def two_passes_lomuto(seq):
    """使用 Lomuto 分区方案执行前两趟"""
    a = list(seq)
    p1 = lomuto_partition(a, 0, len(a) - 1)
    p2 = lomuto_partition(a, 0, p1 - 1) if p1 > 0 else -1
    return a, p1, p2

# ============================================================
# 干扰项 D：第二趟对右侧子序列执行 partition
# ============================================================
def two_passes_right_side(seq):
    """第二趟对右侧子序列（而非左侧）执行 partition"""
    a = list(seq)
    p1 = hoare_partition(a, 0, len(a) - 1)
    # 错误：对右侧子序列执行 partition
    if p1 < len(a) - 1:
        p2 = hoare_partition(a, p1 + 1, len(a) - 1)
    else:
        p2 = -1
    return a, p1, p2

# ============================================================
# 计算所有选项
# ============================================================
print("=" * 60)
print("PARAMS")
print(f"初始序列: {SEQ}")
print(f"序列长度: {len(SEQ)}")
print("=" * 60)

# A: 正确结果
A, p1_a, p2_a = two_passes(SEQ)
print("\nREASONING")
print(f"\n【正确路径 A】")
print(f"  第一趟 partition (pivot=12): pivot 最终位置 = {p1_a}")
print(f"  第一趟后序列: {A}")
print(f"  第二趟 partition (左侧子序列 [0..{p1_a-1}], pivot={A[0]}): pivot 最终位置 = {p2_a}")
print(f"  第二趟后序列: {A}")

# B: 第一趟基准归位错误
B, p1_b, p2_b = two_passes_swap_i(SEQ)
print(f"\n【干扰项 B】第一趟基准与 a[i] 交换（而非 a[j]）")
print(f"  第一趟 pivot 位置 = {p1_b}")
print(f"  结果序列: {B}")

# C: Lomuto 单指针分区
C, p1_c, p2_c = two_passes_lomuto(SEQ)
print(f"\n【干扰项 C】使用 Lomuto 单指针分区方案")
print(f"  第一趟 pivot 位置 = {p1_c}")
print(f"  结果序列: {C}")

# D: 第二趟对右侧子序列
D, p1_d, p2_d = two_passes_right_side(SEQ)
print(f"\n【干扰项 D】第二趟对右侧子序列执行 partition")
print(f"  第一趟 pivot 位置 = {p1_d}")
print(f"  第二趟 pivot 位置 = {p2_d}")
print(f"  结果序列: {D}")

# ============================================================
# 验证
# ============================================================
print("\n" + "=" * 60)
print("ANSWER")
print(f"A = {A}")
print(f"B = {B}")
print(f"C = {C}")
print(f"D = {D}")
print("=" * 60)

# 验证段
print("\n【验证】")

# 验证1: 第一趟分区性质（A 路径）
a_check = list(SEQ)
p1_check = hoare_partition(a_check, 0, len(a_check) - 1)
left_ok = all(a_check[k] < a_check[p1_check] for k in range(0, p1_check))
right_ok = all(a_check[k] > a_check[p1_check] for k in range(p1_check + 1, len(a_check)))
assert left_ok, f"第一趟左侧分区性质不成立: {a_check}"
assert right_ok, f"第一趟右侧分区性质不成立: {a_check}"
print("✓ 第一趟分区性质成立")

# 验证2: 第二趟分区性质（A 路径）
p2_check = hoare_partition(a_check, 0, p1_check - 1) if p1_check > 0 else -1
if p2_check >= 0:
    left2_ok = all(a_check[k] < a_check[p2_check] for k in range(0, p2_check))
    right2_ok = all(a_check[k] > a_check[p2_check] for k in range(p2_check + 1, p1_check))
    assert left2_ok, f"第二趟左侧分区性质不成立: {a_check}"
    assert right2_ok, f"第二趟右侧分区性质不成立: {a_check}"
    print("✓ 第二趟分区性质成立")

# 验证3: 4 选项互异
options = {tuple(A): 'A', tuple(B): 'B', tuple(C): 'C', tuple(D): 'D'}
assert len(options) == 4, f"选项撞值! 仅有 {len(options)} 个不同值: {options}"
print("✓ 4 选项互异")

# 验证4: A 是正确值
assert A == list(a_check), "A 与正确计算结果不一致"
print("✓ A 对应正确值")

print("\n所有验证通过!")
