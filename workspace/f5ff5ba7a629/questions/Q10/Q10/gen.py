"""
快速排序前两趟划分结果 - 参数搜索 + 求解
策略: 取首元素为枢轴, 从右端开始扫描
"""
import random

def partition(arr, lo, hi):
    """
    标准快速排序 Partition:
    - 枢轴 = arr[lo] (首元素)
    - 从右端开始扫描
    - 返回枢轴最终位置 pivot_pos
    - 原地修改 arr[lo..hi]
    执行后 arr[lo..pivot_pos-1] < pivot < arr[pivot_pos+1..hi]
    """
    pivot = arr[lo]
    i = lo
    j = hi
    while i < j:
        # 从右端向左扫描, 找第一个小于枢轴的
        while i < j and arr[j] >= pivot:
            j -= 1
        # 从左端向右扫描, 找第一个大于枢轴的
        while i < j and arr[i] <= pivot:
            i += 1
        if i < j:
            arr[i], arr[j] = arr[j], arr[i]
    # 枢轴归位: 交换 arr[lo] 和 arr[i] (i==j 相遇点)
    arr[lo], arr[i] = arr[i], arr[lo]
    return i

def partition_no_final_swap(arr, lo, hi):
    """
    漏掉枢轴归位交换的版本:
    执行扫描和交换过程, 但最后不把枢轴交换到相遇位置
    返回相遇点位置, 但枢轴仍在 lo
    """
    pivot = arr[lo]
    i = lo
    j = hi
    while i < j:
        while i < j and arr[j] >= pivot:
            j -= 1
        while i < j and arr[i] <= pivot:
            i += 1
        if i < j:
            arr[i], arr[j] = arr[j], arr[i]
    # 不做 arr[lo], arr[i] = arr[i], arr[lo]
    return i

def try_sequence(seq):
    """尝试给定序列, 返回四个选项路径的结果序列, 以及约束是否满足"""
    n = len(seq)
    
    # === 路径A: 正确两趟 ===
    arrA = list(seq)
    # 第一趟: 对全表 [0, n-1]
    p1 = partition(arrA, 0, n-1)
    # 第二趟: 对左子表 [0, p1-1] (优先处理左子表)
    if p1 - 1 >= 0 and (p1 - 1) - 0 + 1 >= 2:
        p2 = partition(arrA, 0, p1-1)
    else:
        return None  # 左子表长度<2, 第二趟无内容
    
    # === 路径B: 只做一趟 ===
    arrB = list(seq)
    partition(arrB, 0, n-1)
    
    # === 路径C: 漏枢轴归位交换 (在第二趟末尾漏) ===
    arrC = list(seq)
    # 第一趟正确
    p1_c = partition(arrC, 0, n-1)
    # 第二趟漏掉最后枢轴归位交换
    left_len = p1_c  # 左子表 [0, p1_c-1] 的长度
    if left_len >= 2:
        partition_no_final_swap(arrC, 0, p1_c-1)
    else:
        return None
    
    # === 路径D: 第二趟对右子表而非左子表 ===
    arrD = list(seq)
    p1_d = partition(arrD, 0, n-1)
    # 右子表 [p1_d+1, n-1]
    right_len = (n-1) - (p1_d+1) + 1
    if right_len >= 2:
        partition(arrD, p1_d+1, n-1)
    else:
        return None  # 右子表也需 >=2 才有区分度
    
    return {
        'seq': list(seq),
        'A': arrA,
        'B': arrB,
        'C': arrC,
        'D': arrD,
        'p1': p1,
    }

def check_constraints(result):
    """检查四路区分度"""
    A, B, C, D = result['A'], result['B'], result['C'], result['D']
    seqs = [('A', A), ('B', B), ('C', C), ('D', D)]
    for i in range(len(seqs)):
        for j in range(i+1, len(seqs)):
            if seqs[i][1] == seqs[j][1]:
                return False, f"{seqs[i][0]} == {seqs[j][0]}"
    return True, "all distinct"

# 搜索满足约束的序列
random.seed(42)
found = None
attempts = 0

while found is None and attempts < 100000:
    attempts += 1
    n = random.randint(8, 10)
    seq = random.sample(range(10, 100), n)
    
    result = try_sequence(seq)
    if result is None:
        continue
    
    ok, msg = check_constraints(result)
    if ok:
        # 额外检查: 左子表长度 >= 2 (保证第二趟有内容)
        if result['p1'] >= 2:
            found = result

if found is None:
    print("未找到满足约束的序列!")
else:
    S = found['seq']
    n = len(S)
    print(f"=== 初始序列 S ===")
    print(f"n = {n}")
    print(f"S = {S}")
    print(f"第一趟枢轴 = {S[0]}, 划分后枢轴位置 = {found['p1']}")
    print(f"左子表长度 = {found['p1']}, 右子表长度 = {n - found['p1'] - 1}")
    print()
    
    print(f"=== 选项 A (正确两趟) ===")
    print(found['A'])
    print()
    print(f"=== 选项 B (只做一趟) ===")
    print(found['B'])
    print()
    print(f"=== 选项 C (漏第二趟枢轴归位) ===")
    print(found['C'])
    print()
    print(f"=== 选项 D (第二趟对右子表) ===")
    print(found['D'])
    print()
    
    # 验证区分度
    ok, msg = check_constraints(found)
    print(f"=== 四路区分度验证 ===")
    print(f"通过: {ok}, {msg}")
    print()
    
    # 打印详细求解过程
    print(f"=== 求解详细过程 ===")
    
    # 第一趟
    arr1 = list(S)
    print(f"初始序列: {arr1}")
    pivot1 = arr1[0]
    print(f"第一趟: 对全表 [{arr1}] 以枢轴 {pivot1} 划分")
    p1 = partition(arr1, 0, n-1)
    print(f"第一趟结果: {arr1}, 枢轴 {pivot1} 归位到位置 {p1}")
    print(f"  左子表 {arr1[0:p1]} (长度 {p1})")
    print(f"  右子表 {arr1[p1+1:n]} (长度 {n-p1-1})")
    
    # 第二趟
    print(f"\n第二趟: 对左子表 {arr1[0:p1]} 以枢轴 {arr1[0]} 划分")
    p2 = partition(arr1, 0, p1-1)
    print(f"第二趟结果: {arr1}")
    print(f"  枢轴 {arr1[p2]} 归位到位置 {p2}")
    
    print(f"\n最终正确序列 (A): {arr1}")
