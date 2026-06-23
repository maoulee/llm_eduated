"""
手动追踪验证 partition 算法
"""

def partition_trace(arr, low, high, pivot_idx, ascending=True):
    """带详细追踪的 partition"""
    pivot = arr[pivot_idx]
    l, h = pivot_idx + 1, high
    print(f"  初始: arr={arr}, pivot={pivot}, l={l}, h={h}")
    
    step = 0
    while l <= h:
        step += 1
        # 右指针扫描
        if ascending:
            while h >= l and arr[h] >= pivot:
                h -= 1
        else:
            while h >= l and arr[h] <= pivot:
                h -= 1
        print(f"  步骤{step}: h扫描到{h}, arr[h]={arr[h]}")
        
        # 左指针扫描
        if ascending:
            while l <= h and arr[l] <= pivot:
                l += 1
        else:
            while l <= h and arr[l] >= pivot:
                l += 1
        print(f"  步骤{step}: l扫描到{l}, arr[l]={arr[l] if l <= high else '越界'}")
        
        if l < h:
            arr[l], arr[h] = arr[h], arr[l]
            print(f"  步骤{step}: 交换arr[{l}]和arr[{h}], arr={arr}")
        else:
            print(f"  步骤{step}: l={l} >= h={h}, 退出循环")
            break
    
    arr[pivot_idx], arr[h] = arr[h], arr[pivot_idx]
    print(f"  基准归位: 交换arr[{pivot_idx}]和arr[{h}], arr={arr}")
    return h


INITIAL = [45, 23, 67, 12, 89, 34, 56, 78, 9, 41]

print("=== 第一趟 partition (pivot=45) ===")
arr1 = list(INITIAL)
pos1 = partition_trace(arr1, 0, 9, 0, True)
print(f"第一趟结果: {arr1}, pivot位置={pos1}")
print()

print("=== 第二趟: 左子区间 [0..{0}] partition (pivot={1}) ===".format(pos1-1, arr1[0]))
arr2 = list(arr1)
partition_trace(arr2, 0, pos1-1, 0, True)
print(f"左子区间partition后: {arr2}")
print()

print("=== 第二趟: 右子区间 [{0}..9] partition (pivot={1}) ===".format(pos1+1, arr1[pos1+1]))
arr3 = list(arr2)
partition_trace(arr3, pos1+1, 9, pos1+1, True)
print(f"右子区间partition后: {arr3}")
print()

print("=== 最终结果 ===")
print(f"第一趟后: {arr1}")
print(f"第二趟后: {arr3}")
