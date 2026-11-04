# 验证脚本 — 手动模拟 Partition 过程

ORIGINAL = [45, 23, 67, 12, 89, 34, 56, 78, 9, 51]

def partition_correct(arr, low, high):
    """严蔚敏标准双指针法：先右后左"""
    pivot = arr[low]
    i, j = low, high
    print(f"  partition({low},{high}), pivot={pivot}")
    while i < j:
        print(f"    i={i}, j={j}, arr={arr}")
        while i < j and arr[j] >= pivot:
            j -= 1
        print(f"    j停: j={j}, arr[j]={arr[j]}")
        while i < j and arr[i] <= pivot:
            i += 1
        print(f"    i停: i={i}, arr[i]={arr[i]}")
        if i < j:
            arr[i], arr[j] = arr[j], arr[i]
            print(f"    交换后: arr={arr}")
    print(f"    i==j={i}, 基准归位")
    arr[low], arr[i] = arr[i], arr[low]
    print(f"    归位后: arr={arr}")
    return i

# 第一趟
print("=== 第一趟 ===")
a1 = list(ORIGINAL)
p1 = partition_correct(a1, 0, len(a1) - 1)
print(f"第一趟结果: {a1}, pivot_idx={p1}")
print()

# 第二趟左
print("=== 第二趟左子序列 [0,{}] ===".format(p1-1))
p2_left = partition_correct(a1, 0, p1 - 1)
print(f"左子序列结果: {a1}, pivot_idx={p2_left}")
print()

# 第二趟右
print("=== 第二趟右子序列 [{},{}] ===".format(p1+1, len(a1)-1))
p2_right = partition_correct(a1, p1 + 1, len(a1) - 1)
print(f"右子序列结果: {a1}, pivot_idx={p2_right}")
print()

print(f"最终结果: {a1}")
