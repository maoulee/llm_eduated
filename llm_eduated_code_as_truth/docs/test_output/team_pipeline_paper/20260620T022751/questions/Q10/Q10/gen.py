import copy

# ============================================================
# 题干参数
# ============================================================
arr = [45, 23, 67, 12, 89, 34]

# ============================================================
# Hoare partition（正确实现）
# ============================================================
def hoare_partition(a, low, high):
    """Hoare方案：pivot=第一个元素，i从low-1开始++直到>=pivot，j从high+1开始--直到<=pivot"""
    pivot = a[low]
    i = low - 1
    j = high + 1
    while True:
        while True:
            i += 1
            if a[i] >= pivot:
                break
        while True:
            j -= 1
            if a[j] <= pivot:
                break
        if i < j:
            a[i], a[j] = a[j], a[i]
        else:
            return j

# ============================================================
# Lomuto partition（干扰项D用）
# ============================================================
def lomuto_partition(a, low, high):
    """Lomuto方案：pivot=最后一个元素"""
    pivot = a[high]
    i = low - 1
    for j in range(low, high):
        if a[j] <= pivot:
            i += 1
            a[i], a[j] = a[j], a[i]
    a[i + 1], a[high] = a[high], a[i + 1]
    return i + 1

# ============================================================
# 错误Hoare：指针移动方向反了（干扰项B用）
# i++直到A[i]<=pivot，j--直到A[j]>=pivot
# ============================================================
def hoare_partition_wrong_direction(a, low, high):
    pivot = a[low]
    i = low - 1
    j = high + 1
    while True:
        while True:
            i += 1
            if a[i] <= pivot:  # 错误：应该是 >=
                break
        while True:
            j -= 1
            if a[j] >= pivot:  # 错误：应该是 <=
                break
        if i < j:
            a[i], a[j] = a[j], a[i]
        else:
            return j

# ============================================================
# 快速排序：只做指定趟数
# ============================================================
def quicksort_two_passes_hoare(a):
    """正确Hoare方案，做两趟"""
    a = copy.deepcopy(a)
    # 第一趟：对整个数组partition
    j = hoare_partition(a, 0, len(a) - 1)
    # 第二趟：对左子数组partition，再对右子数组partition
    if j >= 0:
        j_left = hoare_partition(a, 0, j)
    if j + 1 < len(a) - 1:
        j_right = hoare_partition(a, j + 1, len(a) - 1)
    return a

def quicksort_one_pass_hoare(a):
    """只做了第一趟（干扰项C用）"""
    a = copy.deepcopy(a)
    j = hoare_partition(a, 0, len(a) - 1)
    return a

def quicksort_two_passes_wrong_direction(a):
    """错误指针方向（干扰项B用）"""
    a = copy.deepcopy(a)
    # 第一趟
    j = hoare_partition_wrong_direction(a, 0, len(a) - 1)
    # 第二趟
    if j >= 0:
        j_left = hoare_partition_wrong_direction(a, 0, j)
    if j + 1 < len(a) - 1:
        j_right = hoare_partition_wrong_direction(a, j + 1, len(a) - 1)
    return a

def quicksort_two_passes_lomuto(a):
    """Lomuto方案（干扰项D用）"""
    a = copy.deepcopy(a)
    # 第一趟
    p = lomuto_partition(a, 0, len(a) - 1)
    # 第二趟：对左子数组partition，再对右子数组partition
    if p > 0:
        p_left = lomuto_partition(a, 0, p - 1)
    if p + 1 < len(a) - 1:
        p_right = lomuto_partition(a, p + 1, len(a) - 1)
    return a

# ============================================================
# 计算各选项
# ============================================================
option_a = quicksort_two_passes_hoare(arr)
option_b = quicksort_two_passes_wrong_direction(arr)
option_c = quicksort_one_pass_hoare(arr)
option_d = quicksort_two_passes_lomuto(arr)

# ============================================================
# 输出
# ============================================================
print("PARAMS")
print(f"原始序列: {arr}")
print()

print("REASONING")
print("第一趟Hoare partition (pivot=45):")
a1 = copy.deepcopy(arr)
j1 = hoare_partition(a1, 0, len(a1) - 1)
print(f"  第一趟后: {a1}, 返回j={j1}")
print(f"  左子数组: {a1[0:j1+1]}, 右子数组: {a1[j1+1:]}")

print("第二趟Hoare partition:")
a2 = copy.deepcopy(a1)
if j1 >= 0:
    j_left = hoare_partition(a2, 0, j1)
    print(f"  左子数组partition后: {a2}, 返回j_left={j_left}")
if j1 + 1 < len(a2) - 1:
    j_right = hoare_partition(a2, j1 + 1, len(a2) - 1)
    print(f"  右子数组partition后: {a2}, 返回j_right={j_right}")

print()
print("ANSWER")
print(f"A: {option_a}")
print(f"B: {option_b}")
print(f"C: {option_c}")
print(f"D: {option_d}")

# ============================================================
# 验证
# ============================================================
print()
print("=== 验证 ===")

# 验证1：4选项互异
options = [option_a, option_b, option_c, option_d]
distinct = len(set(tuple(o) for o in options)) == 4
print(f"4选项互异: {distinct}")
assert distinct, "选项有碰撞！"

# 验证2：正确结果排序后等于原序列排序
assert sorted(option_a) == sorted(arr), "正确选项排序后不等于原序列排序"
print("正确选项排序后等于原序列排序: True")

# 验证3：干扰项C（只一趟）与正确结果不同
assert option_c != option_a, "干扰项C与正确结果相同"
print("干扰项C与正确结果不同: True")

# 验证4：干扰项D（Lomuto）与正确结果不同
assert option_d != option_a, "干扰项D与正确结果相同"
print("干扰项D与正确结果不同: True")

# 验证5：干扰项B（方向错误）与正确结果不同
assert option_b != option_a, "干扰项B与正确结果相同"
print("干扰项B与正确结果不同: True")

print("所有验证通过！")
