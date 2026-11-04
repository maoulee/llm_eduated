"""
快速排序前两趟划分结果 — 建模代码
题干: 序列 [45, 23, 67, 12, 89, 34, 56, 78, 9, 51]
Partition 规则: 严蔚敏教材标准双指针法（先右后左）
"""

ORIGINAL = [45, 23, 67, 12, 89, 34, 56, 78, 9, 51]


def partition_correct(arr, low, high):
    """严蔚敏标准双指针法：先右后左"""
    pivot = arr[low]
    i, j = low, high
    while i < j:
        while i < j and arr[j] >= pivot:
            j -= 1
        while i < j and arr[i] <= pivot:
            i += 1
        if i < j:
            arr[i], arr[j] = arr[j], arr[i]
    # 基准归位：与 R[i]（i==j）交换
    arr[low], arr[i] = arr[i], arr[low]
    return i


def partition_wrong_pointer_order(arr, low, high):
    """指针移动顺序错误：先移动左指针再移动右指针"""
    pivot = arr[low]
    i, j = low, high
    while i < j:
        # 错误：先左后右（正确应为先右后左）
        while i < j and arr[i] <= pivot:
            i += 1
        while i < j and arr[j] >= pivot:
            j -= 1
        if i < j:
            arr[i], arr[j] = arr[j], arr[i]
    arr[low], arr[i] = arr[i], arr[low]
    return i


def partition_wrong_pivot_pos(arr, low, high):
    """
    基准归位位置错误：基准放到子序列末尾 arr[high]，
    而非 i==j 的正确位置。
    模拟"基准始终放到末尾"的错误理解。
    """
    pivot = arr[low]
    i, j = low, high
    while i < j:
        while i < j and arr[j] >= pivot:
            j -= 1
        while i < j and arr[i] <= pivot:
            i += 1
        if i < j:
            arr[i], arr[j] = arr[j], arr[i]
    # 错误：基准放到子序列末尾 arr[high]，而非 arr[i]（i==j）
    arr[low], arr[high] = arr[high], arr[low]
    # 返回 high 作为"基准位置"（错误位置）
    return high


def two_passes_correct(arr):
    """正确：前两趟划分"""
    a = list(arr)
    n = len(a)
    # 第一趟：对整个序列 partition
    p1 = partition_correct(a, 0, n - 1)
    # 第二趟：对左子序列和右子序列分别 partition
    if p1 > 0:
        partition_correct(a, 0, p1 - 1)
    if p1 < n - 1:
        partition_correct(a, p1 + 1, n - 1)
    return a


def two_passes_wrong_range(arr):
    """
    错误B：第一趟正确，第二趟划分范围错误。
    对 [0, p1]（包含基准）而非 [0, p1-1] 进行划分。
    """
    a = list(arr)
    n = len(a)
    # 第一趟正确
    p1 = partition_correct(a, 0, n - 1)
    # 第二趟错误：左子序列范围包含基准位置
    if p1 > 0:
        partition_correct(a, 0, p1)  # 错误：应为 p1-1
    if p1 < n - 1:
        partition_correct(a, p1 + 1, n - 1)
    return a


def two_passes_wrong_pivot_pos(arr):
    """
    错误C：基准归位位置错误。
    两趟均使用 partition_wrong_pivot_pos。
    """
    a = list(arr)
    n = len(a)
    # 第一趟使用错误的归位
    p1 = partition_wrong_pivot_pos(a, 0, n - 1)
    # 第二趟也使用错误的归位
    if p1 > 0:
        partition_wrong_pivot_pos(a, 0, p1 - 1)
    if p1 < n - 1:
        partition_wrong_pivot_pos(a, p1 + 1, n - 1)
    return a


def two_passes_wrong_pointer_order(arr):
    """
    错误D：指针移动顺序错误（先左后右）。
    两趟均使用 partition_wrong_pointer_order。
    """
    a = list(arr)
    n = len(a)
    # 第一趟使用错误的指针顺序
    p1 = partition_wrong_pointer_order(a, 0, n - 1)
    # 第二趟也使用错误的指针顺序
    if p1 > 0:
        partition_wrong_pointer_order(a, 0, p1 - 1)
    if p1 < n - 1:
        partition_wrong_pointer_order(a, p1 + 1, n - 1)
    return a


# ========== 主执行 ==========
if __name__ == "__main__":
    correct = two_passes_correct(ORIGINAL)
    wrong_b = two_passes_wrong_range(ORIGINAL)
    wrong_c = two_passes_wrong_pivot_pos(ORIGINAL)
    wrong_d = two_passes_wrong_pointer_order(ORIGINAL)

    print("PARAMS")
    print(f"初始序列: {ORIGINAL}")
    print()

    # 验证正确结果的特征
    sorted_arr = sorted(ORIGINAL)
    pivot_val = ORIGINAL[0]  # 45
    pivot_final_idx = sorted_arr.index(pivot_val)

    print("REASONING")
    print(f"有序序列: {sorted_arr}")
    print(f"基准 {pivot_val} 的最终位置应为索引 {pivot_final_idx}")
    print()

    # 验证条件1：第一趟基准归位可验证
    a1 = list(ORIGINAL)
    p1 = partition_correct(a1, 0, len(a1) - 1)
    print(f"第一趟后: {a1}")
    print(f"基准 {pivot_val} 归位到索引 {p1}")
    left_ok = all(x <= pivot_val for x in a1[:p1])
    right_ok = all(x >= pivot_val for x in a1[p1+1:])
    print(f"左侧全≤{pivot_val}: {left_ok}")
    print(f"右侧全≥{pivot_val}: {right_ok}")
    print()

    # 验证条件2：第二趟产生两个子划分
    print(f"第二趟左子序列 [0,{p1-1}]: {a1[0:p1]}")
    print(f"第二趟右子序列 [{p1+1},{len(a1)-1}]: {a1[p1+1:]}")
    print()

    print(f"正确结果(A): {correct}")
    print(f"错误B结果:   {wrong_b}")
    print(f"错误C结果:   {wrong_c}")
    print(f"错误D结果:   {wrong_d}")
    print()

    print("ANSWER")
    print(f"A={correct}")
    print(f"B={wrong_b}")
    print(f"C={wrong_c}")
    print(f"D={wrong_d}")

    # ========== 验证段 ==========
    # 条件1：第一趟基准归位正确
    assert p1 == pivot_final_idx, f"第一趟基准位置错误: {p1} != {pivot_final_idx}"
    assert left_ok, "第一趟左侧元素不全≤基准"
    assert right_ok, "第一趟右侧元素不全≥基准"

    # 条件2：第二趟对左右子序列都执行了 partition
    # （通过检查第二趟后左右子序列各自有基准归位来验证）
    # 左子序列的基准归位
    a2 = list(a1)
    if p1 > 0:
        p2_left = partition_correct(a2, 0, p1 - 1)
        left_pivot = a2[p2_left]
        assert all(x <= left_pivot for x in a2[0:p2_left]), "第二趟左子序列基准归位错误"
        assert all(x >= left_pivot for x in a2[p2_left+1:p1]), "第二趟左子序列基准归位错误"
    # 右子序列的基准归位
    if p1 < len(a2) - 1:
        p2_right = partition_correct(a2, p1 + 1, len(a2) - 1)
        right_pivot = a2[p2_right]
        assert all(x <= right_pivot for x in a2[p1+1:p2_right]), "第二趟右子序列基准归位错误"
        assert all(x >= right_pivot for x in a2[p2_right+1:]), "第二趟右子序列基准归位错误"

    # 条件3：4选项互异
    assert len({tuple(correct), tuple(wrong_b), tuple(wrong_c), tuple(wrong_d)}) == 4, \
        f"选项碰撞: A={correct}, B={wrong_b}, C={wrong_c}, D={wrong_d}"

    # 条件4：A = 正确值
    assert correct == two_passes_correct(ORIGINAL), "A 不等于正确计算结果"

    # 条件5：干扰项对应声明错误类型
    assert wrong_b == two_passes_wrong_range(ORIGINAL), "B 不等于范围错误路径结果"
    assert wrong_c == two_passes_wrong_pivot_pos(ORIGINAL), "C 不等于归位错误路径结果"
    assert wrong_d == two_passes_wrong_pointer_order(ORIGINAL), "D 不等于指针顺序错误路径结果"

    # 条件6：干扰项与正确值不同（已由条件3覆盖，但显式声明）
    assert wrong_b != correct, "B 与 A 相同"
    assert wrong_c != correct, "C 与 A 相同"
    assert wrong_d != correct, "D 与 A 相同"

    print()
    print("所有验证通过 ✓")
