# -*- coding: utf-8 -*-
"""
直接插入排序与冒泡排序过程对比 — 建模代码
"""

def insertion_sort_passes(arr):
    """直接插入排序，返回每趟结果列表"""
    a = list(arr)
    n = len(a)
    passes = []
    for i in range(1, n):
        key = a[i]
        j = i - 1
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = key
        passes.append(list(a))
    return passes


def bubble_sort_passes(arr):
    """冒泡排序，返回每趟结果列表（提前终止）"""
    a = list(arr)
    n = len(a)
    passes = []
    total_swaps = 0
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swapped = True
                total_swaps += 1
        passes.append(list(a))
        if not swapped:
            break
    return passes, total_swaps


def solve(arr):
    n = len(arr)

    # 直接插入排序
    ins_passes = insertion_sort_passes(arr)

    # 冒泡排序
    bub_passes, bub_swaps = bubble_sort_passes(arr)

    # 最终结果
    ins_final = ins_passes[-1]
    bub_final = bub_passes[-1]
    expected = sorted(arr)

    # ========== 验证段（翻译"通过条件"） ==========

    # 条件1：直接插入排序每趟有序性 — 第i趟结果中，前i+1个元素升序
    for i, p in enumerate(ins_passes):
        prefix = p[:i + 2]  # 第i趟(i从0计)对应前i+2个元素有序
        assert prefix == sorted(prefix), f"插入排序第{i+1}趟前{i+2}个元素未升序: {prefix}"

    # 条件2：冒泡排序每趟沉底性 — 第j趟结果中，末尾j个元素为全局最大j个且升序
    global_sorted = sorted(arr)
    for j, p in enumerate(bub_passes):
        suffix = p[n - (j + 1):]  # 末尾j+1个元素
        expected_suffix = global_sorted[n - (j + 1):]
        assert suffix == expected_suffix, f"冒泡排序第{j+1}趟末尾{j+1}个元素沉底失败: {suffix} != {expected_suffix}"

    # 条件3：最终结果一致性
    assert ins_final == expected, f"插入排序最终结果错误: {ins_final} != {expected}"
    assert bub_final == expected, f"冒泡排序最终结果错误: {bub_final} != {expected}"
    assert ins_final == bub_final, "两种排序最终结果不一致"

    # 条件4：直接插入排序恰好 n-1 趟
    assert len(ins_passes) == n - 1, f"插入排序趟数应为{n-1}，实际{len(ins_passes)}"

    # 条件5：冒泡排序至少有一趟发生交换
    assert bub_swaps >= 1, "冒泡排序未发生任何交换，无实质性操作"

    # 条件6：冒泡排序趟数 ≤ n-1
    assert len(bub_passes) <= n - 1, f"冒泡排序趟数{len(bub_passes)}超过{n-1}"

    return ins_passes, bub_passes, bub_swaps


if __name__ == "__main__":
    arr = [45, 12, 78, 23, 67, 34, 89]
    ins_passes, bub_passes, bub_swaps = solve(arr)

    print("PARAMS:", arr)
    print()
    print("=== 直接插入排序 ===")
    for i, p in enumerate(ins_passes):
        print(f"第{i+1}趟: {p}")
    print()
    print("=== 冒泡排序 ===")
    for i, p in enumerate(bub_passes):
        print(f"第{i+1}趟: {p}")
    print(f"总交换次数: {bub_swaps}")
    print()
    print("REASONING: 两种排序均正确完成，所有通过条件已assert验证。")
    print(f"ANSWER: 插入排序{len(ins_passes)}趟，冒泡排序{len(bub_passes)}趟（交换{bub_swaps}次），最终结果均为{sorted(arr)}")
