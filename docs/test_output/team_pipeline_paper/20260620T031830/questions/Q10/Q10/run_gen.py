"""
快速排序前两趟 partition 模拟
序列: [10, 5, 18, 3, 9, 7, 15, 2, 12, 4]
"""

def partition(arr, low, high, swap_with='j', move_order='i_first'):
    pivot = arr[low]
    i = low + 1
    j = high
    
    while True:
        if move_order == 'j_first':
            while j > low and arr[j] >= pivot:
                j -= 1
            while i <= high and arr[i] <= pivot:
                i += 1
        else:
            while i <= high and arr[i] <= pivot:
                i += 1
            while j > low and arr[j] >= pivot:
                j -= 1
        
        if i < j:
            arr[i], arr[j] = arr[j], arr[i]
        else:
            break
    
    if swap_with == 'i':
        arr[low], arr[i] = arr[i], arr[low]
        return i
    else:
        arr[low], arr[j] = arr[j], arr[low]
        return j


def solve(seq, swap_with='j', move_order='i_first', second_side='left'):
    arr = seq[:]
    n = len(arr)
    
    pivot_pos = partition(arr, 0, n - 1, swap_with, move_order)
    
    if second_side == 'left':
        if pivot_pos > 0:
            partition(arr, 0, pivot_pos - 1, swap_with, move_order)
    else:
        if pivot_pos < n - 1:
            partition(arr, pivot_pos + 1, n - 1, swap_with, move_order)
    
    return arr


SEQ = [10, 5, 18, 3, 9, 7, 15, 2, 12, 4]

A = solve(SEQ, 'j', 'i_first', 'left')
print(f"A = {A}")

B = solve(SEQ, 'i', 'i_first', 'left')
print(f"B = {B}")

C = solve(SEQ, 'j', 'j_first', 'left')
print(f"C = {C}")

D = solve(SEQ, 'j', 'i_first', 'right')
print(f"D = {D}")

# 验证互异
assert len({tuple(A), tuple(B), tuple(C), tuple(D)}) == 4

# 打印中间过程
arr1 = SEQ[:]
pp = partition(arr1, 0, len(arr1) - 1, 'j', 'i_first')
print(f"\n第一趟: pivot={arr1[pp]} 归位到索引 {pp}")
print(f"第一趟后: {arr1}")

arr2 = arr1[:]
if pp > 0:
    pp2 = partition(arr2, 0, pp - 1, 'j', 'i_first')
    print(f"第二趟: pivot={arr2[pp2]} 归位到索引 {pp2}")
    print(f"第二趟后: {arr2}")
