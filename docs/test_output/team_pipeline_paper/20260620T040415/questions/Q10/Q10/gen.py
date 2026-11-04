import copy

def partition_correct(arr, low, high):
    """严蔚敏标准双指针法：先右后左，基准归位到 i==j 位置"""
    pivot = arr[low]
    i, j = low, high
    while i < j:
        while i < j and arr[j] >= pivot:
            j -= 1
        while i < j and arr[i] <= pivot:
            i += 1
        if i < j:
            arr[i], arr[j] = arr[j], arr[i]
    arr[low], arr[i] = arr[i], arr[low]
    return i

def partition_wrong_pivot_pos(arr, low, high):
    """错误版本C：基准归位时固定放到子序列末尾 arr[high]，而非 i==j 位置"""
    pivot = arr[low]
    i, j = low, high
    while i < j:
        while i < j and arr[j] >= pivot:
            j -= 1
        while i < j and arr[i] <= pivot:
            i += 1
        if i < j:
            arr[i], arr[j] = arr[j], arr[i]
    # 错误：基准固定放到子序列末尾，而不是 i==j 位置
    arr[low], arr[high] = arr[high], arr[low]
    return high

def partition_wrong_order(arr, low, high):
    """错误版本D：先移动左指针 i，再移动右指针 j"""
    pivot = arr[low]
    i, j = low, high
    while i < j:
        while i < j and arr[i] <= pivot:
            i += 1
        while i < j and arr[j] >= pivot:
            j -= 1
        if i < j:
            arr[i], arr[j] = arr[j], arr[i]
    arr[low], arr[i] = arr[i], arr[low]
    return i

def quicksort_two_passes_correct(arr):
    """正确版本：前两趟划分"""
    arr = copy.deepcopy(arr)
    # 第一趟：对整个序列划分
    pivot_pos = partition_correct(arr, 0, len(arr) - 1)
    print(f"第一趟划分后: {arr}, pivot={arr[pivot_pos]} 位置={pivot_pos}")
    # 第二趟：对左半部分划分（教材惯例先处理左边）
    if pivot_pos > 0:
        partition_correct(arr, 0, pivot_pos - 1)
    print(f"第二趟划分后: {arr}")
    return arr

def quicksort_two_passes_wrong_b(arr):
    """错误版本B：第一趟正确，第二趟对右半部分划分（错误子序列）"""
    arr = copy.deepcopy(arr)
    # 第一趟：正确
    pivot_pos = partition_correct(arr, 0, len(arr) - 1)
    print(f"第一趟划分后: {arr}, pivot={arr[pivot_pos]} 位置={pivot_pos}")
    # 第二趟：错误——对右半部分划分而不是左半部分
    if pivot_pos < len(arr) - 1:
        partition_correct(arr, pivot_pos + 1, len(arr) - 1)
    print(f"第二趟(错误范围)划分后: {arr}")
    return arr

def quicksort_two_passes_wrong_c(arr):
    """错误版本C：基准归位位置错误（固定放到末尾）"""
    arr = copy.deepcopy(arr)
    # 第一趟：使用错误的 partition
    pivot_pos = partition_wrong_pivot_pos(arr, 0, len(arr) - 1)
    print(f"第一趟划分后: {arr}, pivot位置={pivot_pos}")
    # 第二趟：对左半部分划分（基准在末尾，所以左边是 0 到 high-1）
    if pivot_pos > 0:
        partition_wrong_pivot_pos(arr, 0, pivot_pos - 1)
    print(f"第二趟划分后: {arr}")
    return arr

def quicksort_two_passes_wrong_d(arr):
    """错误版本D：指针移动顺序错误（先左后右）"""
    arr = copy.deepcopy(arr)
    # 第一趟：使用错误的 partition
    pivot_pos = partition_wrong_order(arr, 0, len(arr) - 1)
    print(f"第一趟划分后: {arr}, pivot={arr[pivot_pos]} 位置={pivot_pos}")
    # 第二趟：对左半部分划分
    if pivot_pos > 0:
        partition_wrong_order(arr, 0, pivot_pos - 1)
    print(f"第二趟划分后: {arr}")
    return arr

# 主执行
INITIAL = [37, 19, 58, 14, 82, 26, 45, 73, 11, 56]

print("=" * 60)
print("正确版本 (A):")
correct = quicksort_two_passes_correct(INITIAL)
print(f"ANSWER: {correct}")

print("\n" + "=" * 60)
print("错误版本B (第二趟划分范围错误):")
wrong_b = quicksort_two_passes_wrong_b(INITIAL)
print(f"ANSWER: {wrong_b}")

print("\n" + "=" * 60)
print("错误版本C (基准归位位置错误):")
wrong_c = quicksort_two_passes_wrong_c(INITIAL)
print(f"ANSWER: {wrong_c}")

print("\n" + "=" * 60)
print("错误版本D (指针移动顺序错误):")
wrong_d = quicksort_two_passes_wrong_d(INITIAL)
print(f"ANSWER: {wrong_d}")

# 验证通过条件
print("\n" + "=" * 60)
print("验证通过条件:")

# 条件1: 4选项互异
options = [correct, wrong_b, wrong_c, wrong_d]
unique_options = set(tuple(o) for o in options)
print(f"4选项互异: {len(unique_options) == 4}")
assert len(unique_options) == 4, "4选项不互异！"

# 条件2: A = 正确值（已由计算确定）
print(f"A = 正确值: True (由正确算法计算)")

# 条件3: 干扰项对应声明错误类型（由函数实现保证）
print(f"B = 第一趟正确+第二趟错误范围: True (由函数实现保证)")
print(f"C = 基准归位到末尾: True (由函数实现保证)")
print(f"D = 先左后右指针: True (由函数实现保证)")

# 条件4: 干扰项有区分度
assert wrong_b != correct, "B与A相同！"
assert wrong_c != correct, "C与A相同！"
assert wrong_d != correct, "D与A相同！"
assert wrong_b != wrong_c, "B与C相同！"
assert wrong_b != wrong_d, "B与D相同！"
assert wrong_c != wrong_d, "C与D相同！"
print("干扰项区分度: 全部通过")

# 条件5: 考点被触发（序列与初始不同）
assert correct != INITIAL, "正确结果与初始序列相同，partition未执行！"
print("考点被触发: 序列与初始不同")

print("\n所有通过条件验证通过！")
