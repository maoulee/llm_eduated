"""详细打印第一趟和第二趟的每步交换过程"""
S = [74, 87, 35, 29, 57, 30, 79, 77, 10, 86]

def partition_verbose(arr, lo, hi):
    pivot = arr[lo]
    i = lo
    j = hi
    print(f"  枢轴 pivot = arr[{lo}] = {pivot}")
    step = 0
    while i < j:
        while i < j and arr[j] >= pivot:
            j -= 1
        while i < j and arr[i] <= pivot:
            i += 1
        if i < j:
            step += 1
            print(f"  交换 arr[{i}]={arr[i]} 与 arr[{j}]={arr[j]}: {arr} → ", end="")
            arr[i], arr[j] = arr[j], arr[i]
            print(f"{arr}")
    step += 1
    print(f"  指针相遇于位置 {i}, arr[{i}]={arr[i]}")
    print(f"  枢轴归位: 交换 arr[{lo}]={arr[lo]} 与 arr[{i}]={arr[i]}", end="")
    arr[lo], arr[i] = arr[i], arr[lo]
    print(f" → {arr}")
    print(f"  枢轴 {pivot} 归位到位置 {i}")
    return i

print("=== 第一趟: 对全表 [0, 9] ===")
print(f"  初始: {S}")
arr = list(S)
p1 = partition_verbose(arr, 0, 9)
print(f"  第一趟结果: {arr}")
print(f"  左子表: {arr[0:p1]}, 右子表: {arr[p1+1:]}")
print()

print("=== 第二趟: 对左子表 [0, 4] ===")
print(f"  左子表: {arr[0:p1]}")
p2 = partition_verbose(arr, 0, p1-1)
print(f"  第二趟结果: {arr}")
print()

# 路径C: 漏第二趟枢轴归位
print("=== 路径C验证: 第一趟正确, 第二趟漏枢轴归位 ===")
arrC = list(S)
p1c = partition_verbose(arrC, 0, 9)
print(f"  第一趟后: {arrC}")
# 第二趟不做最后交换
pivot = arrC[0]
i, j = 0, p1c-1
while i < j:
    while i < j and arrC[j] >= pivot:
        j -= 1
    while i < j and arrC[i] <= pivot:
        i += 1
    if i < j:
        arrC[i], arrC[j] = arrC[j], arrC[i]
print(f"  扫描相遇于 {i}, 但不交换枢轴 → {arrC}")
print(f"  (枢轴 {pivot} 仍在位置0, 未归位)")
