# -*- coding: utf-8 -*-
"""
综合题：直接插入排序与冒泡排序的逐趟推演与对比
题干规则 → 代码翻译；通过条件 → assert
"""

S = [14, 27, 78, 93, 58, 45, 81, 96]
n = len(S)
expected = sorted(S)

# ============================================================
# 第 1 问：直接插入排序逐趟
# 规则：从第2个元素开始，每趟将当前元素与已排序区从后向前比较，
#       遇到比它大的后移，直到找到正确位置后插入。
# ============================================================
def insertion_sort(arr):
    a = list(arr)
    passes = []          # 每趟后完整序列
    shift_counts = []    # 每趟后移次数
    for i in range(1, len(a)):
        key = a[i]
        j = i - 1
        shifts = 0
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            j -= 1
            shifts += 1
        a[j + 1] = key
        passes.append(list(a))
        shift_counts.append(shifts)
    return passes, shift_counts

ins_passes, ins_shifts = insertion_sort(S)

print("=" * 60)
print("PARAMS")
print(f"  S = {S}")
print(f"  n = {n}")
print(f"  升序目标 expected = {expected}")
print()

print("Q1 - 直接插入排序逐趟结果：")
for idx, p in enumerate(ins_passes):
    print(f"  第 {idx+1} 趟（插入元素 {S[idx+1]}）：{p}")
    print(f"         本趟后移次数 = {ins_shifts[idx]}")
ins_total_shifts = sum(ins_shifts)
print(f"  元素后移总次数 = {ins_total_shifts}")
print()

# ============================================================
# 第 2 问：冒泡排序逐趟
# 规则：每趟从左到右比较相邻元素，前者>后者则交换；
#       若某趟无交换则排序终止。
# ============================================================
def bubble_sort(arr):
    a = list(arr)
    passes = []          # 每趟后完整序列
    swap_counts = []     # 每趟交换次数
    is_sorted = False
    while not is_sorted:
        is_sorted = True
        swaps = 0
        for j in range(0, len(a) - 1):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                is_sorted = False
                swaps += 1
        passes.append(list(a))
        swap_counts.append(swaps)
        if is_sorted:
            break
    return passes, swap_counts

bub_passes, bub_swaps = bubble_sort(S)

print("Q2 - 冒泡排序逐趟结果：")
for idx, p in enumerate(bub_passes):
    tag = ""
    if bub_swaps[idx] == 0:
        tag = "  本趟无交换，排序结束"
    print(f"  第 {idx+1} 趟（交换次数 {bub_swaps[idx]}）：{p}{tag}")
bub_total_swaps = sum(bub_swaps)
print(f"  交换总次数 = {bub_total_swaps}")
print()

# ============================================================
# 第 3 问：对比分析
# ============================================================
ins_num_passes = len(ins_passes)      # 直接插入趟数
bub_num_passes = len(bub_passes)      # 冒泡趟数（含终止趟）

print("Q3 - 对比分析：")
print(f"  直接插入排序实际趟数 = {ins_num_passes}")
print(f"  冒泡排序实际趟数     = {bub_num_passes}")
if ins_num_passes < bub_num_passes:
    print("  趟数更少：直接插入排序")
elif bub_num_passes < ins_num_passes:
    print("  趟数更少：冒泡排序")
else:
    print("  趟数相等")
print(f"  元素后移总次数 = {ins_total_shifts}")
print(f"  交换总次数     = {bub_total_swaps}")
if ins_total_shifts > bub_total_swaps:
    comparison = "大于"
elif ins_total_shifts < bub_total_swaps:
    comparison = "小于"
else:
    comparison = "等于"
print(f"  后移总次数 vs 交换总次数：{comparison}")
print()

# ============================================================
# 逆序对数
# ============================================================
def inversion_count(arr):
    cnt = 0
    for i in range(len(arr)):
        for j in range(i + 1, len(arr)):
            if arr[i] > arr[j]:
                cnt += 1
    return cnt

inv = inversion_count(S)
print(f"REASONING: 初始序列逆序对数 = {inv}")
print()

# ============================================================
# ANSWER 汇总
# ============================================================
print("=" * 60)
print("ANSWER")
print(f"Q1 直接插入排序共 {ins_num_passes} 趟，最终结果 = {ins_passes[-1]}")
print(f"Q2 冒泡排序共 {bub_num_passes} 趟，最终结果 = {bub_passes[-1]}")
print(f"Q3 直接插入趟数={ins_num_passes}, 冒泡趟数={bub_num_passes}, 趟数更少者={'直接插入排序' if ins_num_passes<bub_num_passes else '冒泡排序' if bub_num_passes<ins_num_passes else '相等'}")
print(f"Q3 最坏时间复杂度：直接插入排序 O(n^2)，冒泡排序 O(n^2)")
print(f"Q3 后移总次数({ins_total_shifts}) {comparison} 交换总次数({bub_total_swaps})")
print("=" * 60)

# ============================================================
# 通过条件 → assert（逐条翻译）
# ============================================================
# 条件1：两种排序最终结果一致，均为升序
assert ins_passes[-1] == expected, f"条件1失败：插入排序最终结果 {ins_passes[-1]} != {expected}"
assert bub_passes[-1] == expected, f"条件1失败：冒泡排序最终结果 {bub_passes[-1]} != {expected}"

# 条件2：直接插入趟数=7，每趟序列长度8，已排序区递增
assert ins_num_passes == 7, f"条件2失败：插入排序趟数 {ins_num_passes} != 7"
for idx, p in enumerate(ins_passes):
    assert len(p) == 8, f"条件2失败：第{idx+1}趟序列长度 {len(p)} != 8"
    # 已排序区长度 = idx+2，已排序区应递增
    sorted_zone = p[:idx + 2]
    assert sorted_zone == sorted(sorted_zone), f"条件2失败：第{idx+1}趟已排序区非递增 {sorted_zone}"

# 条件3：冒泡排序趟数 >= 4
assert bub_num_passes >= 4, f"条件3失败：冒泡排序趟数 {bub_num_passes} < 4"

# 条件4：逆序对数 ∈ [3, 6]
assert 3 <= inv <= 6, f"条件4失败：逆序对数 {inv} 不在 [3,6]"

# 条件5：直接插入每趟严格推进——已排序区长度每趟+1
for idx, p in enumerate(ins_passes):
    sorted_zone = p[:idx + 2]
    assert len(sorted_zone) == idx + 2, f"条件5失败：第{idx+1}趟已排序区长度异常"

# 条件6：冒泡每趟有交换或明确终止（除最后一趟外每趟>=1交换；无交换则终止）
for idx in range(len(bub_swaps)):
    if idx < len(bub_swaps) - 1:
        assert bub_swaps[idx] >= 1, f"条件6失败：第{idx+1}趟交换数 {bub_swaps[idx]} < 1 但非最后趟"
    else:
        assert bub_swaps[idx] == 0, f"条件6失败：最后趟交换数 {bub_swaps[idx]} != 0（未正常终止）"

# 条件7：Q3 答案确定性（趟数比较有明确结论，比较结果非"等于"——若有歧义则退化）
assert comparison in ("大于", "小于", "等于"), "条件7失败：比较结果无确定值"
assert ins_num_passes != bub_num_passes, f"条件7失败：两趟数相等({ins_num_passes})，Q3比较退化为'等于'"

print("\n>>> 全部 assert 通过 <<<")
