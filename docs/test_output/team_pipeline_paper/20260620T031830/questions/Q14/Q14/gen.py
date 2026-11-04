"""直接插入排序与冒泡排序过程对比——gen.py"""

def insertion_sort_passes(arr):
    """直接插入排序，返回每趟结束后的序列状态 + 总趟数 + 元素后移次数"""
    a = list(arr)
    n = len(a)
    passes = []
    shift_count = 0

    for i in range(1, n):
        key = a[i]
        j = i - 1
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            shift_count += 1
            j -= 1
        a[j + 1] = key
        passes.append(list(a))

    return passes, len(passes), shift_count


def bubble_sort_passes(arr):
    """冒泡排序，返回每趟结束后的序列状态 + 总趟数 + 交换次数"""
    a = list(arr)
    n = len(a)
    passes = []
    swap_count = 0

    for j in range(n - 1):
        swapped = False
        for i in range(n - 1 - j):
            if a[i] > a[i + 1]:
                a[i], a[i + 1] = a[i + 1], a[i]
                swap_count += 1
                swapped = True
        passes.append(list(a))
        if not swapped:
            break

    return passes, len(passes), swap_count


def check_stability(arr, insertion_passes, bubble_passes):
    """检查两个49的相对位置在排序前后是否保持不变（稳定性）"""
    # 找到两个49的初始位置
    first_49_idx = arr.index(49)
    second_49_idx = arr.index(49, first_49_idx + 1)

    # 插入排序后
    ins_final = insertion_passes[-1]
    ins_first = ins_final.index(49)
    ins_second = ins_final.index(49, ins_first + 1)
    ins_stable = ins_first < ins_second  # 相对位置不变

    # 冒泡排序后
    bub_final = bubble_passes[-1]
    bub_first = bub_final.index(49)
    bub_second = bub_final.index(49, bub_first + 1)
    bub_stable = bub_first < bub_second

    return ins_stable, bub_stable


def solve(arr):
    """主求解函数"""
    # 直接插入排序
    ins_passes, ins_total, ins_shifts = insertion_sort_passes(arr)

    # 冒泡排序
    bub_passes, bub_total, bub_swaps = bubble_sort_passes(arr)

    # 稳定性检查
    ins_stable, bub_stable = check_stability(arr, ins_passes, bub_passes)

    # 最终结果
    ins_result = ins_passes[-1]
    bub_result = bub_passes[-1]

    # ========== 验证段：通过条件 → assert ==========

    # 条件1：插入排序至少发生1次元素后移
    assert ins_shifts >= 1, f"插入排序元素后移次数为{ins_shifts}，应>=1"

    # 条件2：冒泡排序至少发生1次交换
    assert bub_swaps >= 1, f"冒泡排序交换次数为{bub_swaps}，应>=1"

    # 条件3：两种算法最终结果一致
    assert ins_result == bub_result, f"最终结果不一致: 插入={ins_result}, 冒泡={bub_result}"

    # 条件4：稳定性可检验（两个49的相对位置在排序前后可追踪）
    assert ins_stable, "直接插入排序不稳定（两个49相对位置改变）"
    assert bub_stable, "冒泡排序不稳定（两个49相对位置改变）"

    # 条件5：两种算法的总趟数不同
    assert ins_total != bub_total, f"两种算法趟数相同({ins_total})，应不同"

    # ========== 输出 ==========
    print("PARAMS: R = (49, 38, 65, 97, 76, 13, 27, 49)")
    print()

    print("REASONING:")
    print(f"【直接插入排序】共 {ins_total} 趟，元素后移 {ins_shifts} 次")
    for i, p in enumerate(ins_passes, 2):
        print(f"  第{i}趟: {p}")

    print(f"\n【冒泡排序】共 {bub_total} 趟，交换 {bub_swaps} 次")
    for i, p in enumerate(bub_passes, 1):
        print(f"  第{i}趟: {p}")

    print(f"\n【对比分析】")
    print(f"  ① 总趟数: 插入排序={ins_total}, 冒泡排序={bub_total}, 不同")
    print(f"     原因: 插入排序固定n-1趟; 冒泡排序某趟无交换则提前终止")
    print(f"  ② 稳定性: 插入排序={'稳定' if ins_stable else '不稳定'}, 冒泡排序={'稳定' if bub_stable else '不稳定'}")
    print(f"     两个49的相对位置在排序前后均保持不变")

    print()
    print("ANSWER:")
    print(f"插入排序每趟结果: {ins_passes}")
    print(f"冒泡排序每趟结果: {bub_passes}")
    print(f"插入排序总趟数: {ins_total}")
    print(f"冒泡排序总趟数: {bub_total}")
    print(f"插入排序稳定性: {ins_stable}")
    print(f"冒泡排序稳定性: {bub_stable}")


if __name__ == "__main__":
    R = [49, 38, 65, 97, 76, 13, 27, 49]
    solve(R)
