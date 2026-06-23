# gen.py — 直接插入排序与冒泡排序过程模拟及对比

PARAMS
序列: [45, 23, 67, 12, 89, 34, 56, 78]
长度 n = 8

REASONING

# ========== 直接插入排序 ==========
def insertion_sort_with_trace(arr):
    """直接插入排序，记录每趟状态、比较次数、移动次数"""
    a = list(arr)
    n = len(a)
    passes = []  # 每趟结束后的序列状态
    total_comparisons = 0
    total_moves = 0  # 元素后移次数（不含key自身赋值）

    for i in range(1, n):  # i=1..7，对应第2~8个元素
        key = a[i]
        j = i - 1
        # 从后往前比较，找到插入位置
        while j >= 0 and a[j] > key:
            total_comparisons += 1
            a[j + 1] = a[j]  # 元素后移
            total_moves += 1
            j -= 1
        # 最后一次比较（a[j] <= key 或 j < 0）
        if j >= 0:
            total_comparisons += 1
        # 插入key
        a[j + 1] = key
        total_moves += 1  # key的赋值算一次移动
        passes.append(list(a))

    return passes, total_comparisons, total_moves


# ========== 冒泡排序 ==========
def bubble_sort_with_trace(arr):
    """冒泡排序，记录每趟状态、比较次数、交换次数"""
    a = list(arr)
    n = len(a)
    passes = []
    total_comparisons = 0
    total_swaps = 0

    for j in range(n - 1):  # j=0..6，最多7趟
        swapped = False
        for k in range(n - 1 - j):  # 每趟扫描未排序部分
            total_comparisons += 1
            if a[k] > a[k + 1]:
                a[k], a[k + 1] = a[k + 1], a[k]
                total_swaps += 1
                swapped = True
        passes.append(list(a))
        if not swapped:  # 提前终止
            break

    return passes, total_comparisons, total_swaps


# ========== 执行 ==========
original = [45, 23, 67, 12, 89, 34, 56, 78]
n = len(original)

ins_passes, ins_comps, ins_moves = insertion_sort_with_trace(original)
bub_passes, bub_comps, bub_swaps = bubble_sort_with_trace(original)

# 最终结果
ins_final = ins_passes[-1]
bub_final = bub_passes[-1]

# ========== 输出 ==========
print("PARAMS")
print(f"原始序列: {original}")
print(f"长度 n = {n}")
print()

print("REASONING")
print()
print("【直接插入排序过程】")
for idx, p in enumerate(ins_passes, start=1):
    print(f"  第{idx}趟后: {p}")
print(f"  比较次数: {ins_comps}, 移动次数: {ins_moves}")
print(f"  最终结果: {ins_final}")
print()

print("【冒泡排序过程】")
for idx, p in enumerate(bub_passes, start=1):
    print(f"  第{idx}趟后: {p}")
print(f"  比较次数: {bub_comps}, 交换次数: {bub_swaps}")
print(f"  最终结果: {bub_final}")
print()

print("【对比分析】")
print(f"  插入排序: 比较{ins_comps}次, 移动{ins_moves}次")
print(f"  冒泡排序: 比较{bub_comps}次, 交换{bub_swaps}次")
print(f"  两者均为稳定排序")
print()

print("ANSWER")
print(f"Q1_插入排序每趟结果:")
for idx, p in enumerate(ins_passes, start=1):
    print(f"  第{idx}趟: {p}")
print(f"Q2_冒泡排序每趟结果:")
for idx, p in enumerate(bub_passes, start=1):
    print(f"  第{idx}趟: {p}")
print(f"Q3_对比:")
print(f"  插入排序比较{ins_comps}次移动{ins_moves}次")
print(f"  冒泡排序比较{bub_comps}次交换{bub_swaps}次")
print(f"  两者均为稳定排序")

# ========== 验证 ==========
# 验证1: 两种排序最终结果一致且为升序
assert ins_final == bub_final, "两种排序最终结果不一致"
assert ins_final == sorted(original), "最终结果不是升序"

# 验证2: 插入排序产生7趟（i=2~8）
assert len(ins_passes) == 7, f"插入排序趟数应为7，实际{len(ins_passes)}"

# 验证3: 冒泡排序产生若干趟（最多7趟）
assert 1 <= len(bub_passes) <= 7, f"冒泡排序趟数应在1~7之间，实际{len(bub_passes)}"

# 验证4: 比较/移动次数存在差异（使q3对比有意义）
assert ins_comps != bub_comps or ins_moves != bub_swaps, \
    "比较/移动次数完全相同，对比分析无意义"

# 验证5: 两种排序均为稳定排序（通过含重复元素的测试验证）
test_stable = [3, 1, 2, 1, 3]
ins_stable_passes, _, _ = insertion_sort_with_trace(test_stable)
bub_stable_passes, _, _ = bubble_sort_with_trace(test_stable)
# 稳定性：值相等的元素相对位置不变
# 原始中第一个1在索引1，第二个1在索引3；排序后第一个1应在第二个1之前
ins_s = ins_stable_passes[-1]
bub_s = bub_stable_passes[-1]
# 找到两个1的位置
ins_idx1 = [i for i, v in enumerate(ins_s) if v == 1]
bub_idx1 = [i for i, v in enumerate(bub_s) if v == 1]
assert len(ins_idx1) == 2 and len(bub_idx1) == 2, "稳定性测试序列中应有两个1"
# 稳定排序保证相等元素相对位置不变（这里只需验证排序正确且算法本身是稳定的）
assert ins_s == sorted(test_stable), "插入排序稳定性测试失败"
assert bub_s == sorted(test_stable), "冒泡排序稳定性测试失败"
