"""
快速排序前两趟划分结果 — 建模代码
严蔚敏《数据结构》双指针法（左右指针法）
"""

def partition(arr, low, high, pivot_idx, ascending=True):
    """
    严蔚敏双指针法 partition
    pivot_idx: 基准在 arr 中的索引（通常是子区间首元素）
    ascending: True=升序, False=降序
    返回基准归位后的索引
    """
    pivot = arr[pivot_idx]
    # 将基准暂存，low 从 pivot 下一个位置开始，high 从末尾开始
    l, h = pivot_idx + 1, high
    
    while l <= h:
        # 右指针从右向左扫描
        if ascending:
            while h >= l and arr[h] >= pivot:
                h -= 1
        else:
            while h >= l and arr[h] <= pivot:
                h -= 1
        
        # 左指针从左向右扫描
        if ascending:
            while l <= h and arr[l] <= pivot:
                l += 1
        else:
            while l <= h and arr[l] >= pivot:
                l += 1
        
        if l < h:
            arr[l], arr[h] = arr[h], arr[l]
    
    # 基准归位：与 l（即 h）位置交换
    arr[pivot_idx], arr[h] = arr[h], arr[pivot_idx]
    return h


def quicksort_two_rounds(arr, pivot_rule='first', ascending=True, second_round_both=True):
    """
    模拟快速排序前两趟 partition
    pivot_rule: 'first' 或 'last'
    ascending: 排序方向
    second_round_both: 第二趟是否对左右两个子区间都 partition
    返回 (第一趟后序列, 第二趟后序列)
    """
    arr = list(arr)
    n = len(arr)
    
    # 第一趟：对整个数组 partition
    if pivot_rule == 'first':
        pivot_idx = 0
    else:
        pivot_idx = n - 1
    
    pivot_pos = partition(arr, 0, n - 1, pivot_idx, ascending)
    after_first = list(arr)
    
    # 第二趟：对左右两个子区间分别 partition
    if pivot_pos > 0:
        left_pivot_idx = 0 if pivot_rule == 'first' else pivot_pos - 1
        partition(arr, 0, pivot_pos - 1, left_pivot_idx, ascending)
    
    if second_round_both and pivot_pos < n - 1:
        right_pivot_idx = pivot_pos + 1 if pivot_rule == 'first' else n - 1
        partition(arr, pivot_pos + 1, n - 1, right_pivot_idx, ascending)
    
    after_second = list(arr)
    return after_first, after_second


# 初始序列
INITIAL = [45, 23, 67, 12, 89, 34, 56, 78, 9, 41]

print("=== PARAMS ===")
print(f"初始序列: {INITIAL}")
print(f"序列长度: {len(INITIAL)}")
print(f"基准选择: 第一个元素")
print(f"排序方向: 升序")
print(f"Partition算法: 严蔚敏双指针法")

# A: 正确结果
after_first_A, after_second_A = quicksort_two_rounds(
    INITIAL, pivot_rule='first', ascending=True, second_round_both=True
)
print("\n=== REASONING ===")
print(f"第一趟 partition 后: {after_first_A}")
print(f"第二趟 partition 后: {after_second_A}")

# 验证第一趟基准归位
pivot_A = INITIAL[0]  # 45
pos_A = after_first_A.index(pivot_A)
left_of_pivot = after_first_A[:pos_A]
right_of_pivot = after_first_A[pos_A+1:]
assert all(x < pivot_A for x in left_of_pivot), f"第一趟基准左侧有 >= {pivot_A} 的元素"
assert all(x > pivot_A for x in right_of_pivot), f"第一趟基准右侧有 <= {pivot_A} 的元素"
print(f"✓ 第一趟基准 {pivot_A} 归位正确（左侧全<{pivot_A}，右侧全>{pivot_A}）")

# 验证第二趟两个子区间基准均归位
# 左子区间基准
left_pivot_A = after_first_A[0]
left_sub = after_second_A[:pos_A]
left_pivot_pos = left_sub.index(left_pivot_A)
assert all(x < left_pivot_A for x in left_sub[:left_pivot_pos]), "左子区间基准归位错误"
assert all(x > left_pivot_A for x in left_sub[left_pivot_pos+1:]), "左子区间基准归位错误"
print(f"✓ 第二趟左子区间基准 {left_pivot_A} 归位正确")

# 右子区间基准
right_pivot_A = after_first_A[pos_A + 1]
right_sub = after_second_A[pos_A+1:]
right_pivot_pos = right_sub.index(right_pivot_A)
assert all(x < right_pivot_A for x in right_sub[:right_pivot_pos]), "右子区间基准归位错误"
assert all(x > right_pivot_A for x in right_sub[right_pivot_pos+1:]), "右子区间基准归位错误"
print(f"✓ 第二趟右子区间基准 {right_pivot_A} 归位正确")

# B: 基准选择错误（误取最后一个元素为基准）
_, after_second_B = quicksort_two_rounds(
    INITIAL, pivot_rule='last', ascending=True, second_round_both=True
)
print(f"\n干扰项B（基准选最后一个）: {after_second_B}")

# C: 第二趟只对左子区间 partition（漏掉右子区间）
_, after_second_C = quicksort_two_rounds(
    INITIAL, pivot_rule='first', ascending=True, second_round_both=False
)
print(f"干扰项C（第二趟只partition左子区间）: {after_second_C}")

# D: 排序方向搞反（降序而非升序）
_, after_second_D = quicksort_two_rounds(
    INITIAL, pivot_rule='first', ascending=False, second_round_both=True
)
print(f"干扰项D（降序）: {after_second_D}")

# 验证4选项互异
options = [after_second_A, after_second_B, after_second_C, after_second_D]
for i in range(4):
    for j in range(i+1, 4):
        assert options[i] != options[j], f"选项{i+1}和选项{j+1}碰撞！"
print("\n✓ 4个选项互异，无碰撞")

# 验证干扰项对应声明的错误类型
# B: 若用最后一个元素为基准，第一趟基准应为41
after_first_B, _ = quicksort_two_rounds(
    INITIAL, pivot_rule='last', ascending=True, second_round_both=True
)
pivot_B = INITIAL[-1]  # 41
pos_B = after_first_B.index(pivot_B)
assert all(x < pivot_B for x in after_first_B[:pos_B]) or all(x > pivot_B for x in after_first_B[:pos_B]), \
    "B选项第一趟基准归位不符合'选最后一个'的规则"
print("✓ B选项对应'基准选最后一个'的错误路径")

# C: 第二趟只partition左子区间，右子区间应保持第一趟后的状态
assert after_second_C[pos_A+1:] == after_first_A[pos_A+1:], \
    "C选项右子区间应保持不变"
print("✓ C选项对应'第二趟漏掉右子区间'的错误路径")

# D: 降序排序，第一趟基准归位后左侧应全>45，右侧全<45
after_first_D, _ = quicksort_two_rounds(
    INITIAL, pivot_rule='first', ascending=False, second_round_both=True
)
pos_D = after_first_D.index(pivot_A)
assert all(x > pivot_A for x in after_first_D[:pos_D]), "D选项降序第一趟基准归位错误"
assert all(x < pivot_A for x in after_first_D[pos_D+1:]), "D选项降序第一趟基准归位错误"
print("✓ D选项对应'排序方向搞反'的错误路径")

print("\n=== ANSWER ===")
print(f"A: {after_second_A}")
print(f"B: {after_second_B}")
print(f"C: {after_second_C}")
print(f"D: {after_second_D}")
print(f"正确答案: A")
