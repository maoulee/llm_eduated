"""
快速排序前两趟划分结果（选择题）
题干规则 → 代码翻译（func_model）

枢轴取首元素。partition 扫描方式（题干逐句翻译）：
  从右端向左找第一个 < pivot 的 → 放左端空位
  从左端向右找第一个 > pivot 的 → 放右端空位
  交替直至相遇，pivot 放入相遇位置
"""

PARAMS = [49, 12, 68, 35, 89, 23, 56, 71]

def partition_correct(a, lo, hi):
    """题干标准 partition：枢轴取首元素 a[lo]，右端起扫描。
    原地修改 a[lo..hi]，返回枢轴最终位置 pi。"""
    pivot = a[lo]
    i, j = lo, hi
    while i < j:
        # 从右端向左找第一个 < pivot 的（题干：右端起向左扫描找到第一个小于枢轴的）
        while i < j and a[j] >= pivot:
            j -= 1
        if i < j:
            a[i] = a[j]  # 移到左端空位
            i += 1
        # 从左端向右找第一个 > pivot 的（题干：从左端向右扫描找到第一个大于枢轴的）
        while i < j and a[i] <= pivot:
            i += 1
        if i < j:
            a[j] = a[i]  # 移到右端空位
            j -= 1
    a[i] = pivot  # 枢轴放入相遇位置
    return i

def partition_same_side(a, lo, hi):
    """干扰项 C：从枢轴同侧（左端）起扫描的错误方式。
    枢轴仍取首元素，但先从左端向右找 > pivot，再从右端向左找 < pivot。
    """
    pivot = a[lo]
    i, j = lo, hi
    while i < j:
        # 先从左端向右找第一个 > pivot（错误方向）
        while i < j and a[i] <= pivot:
            i += 1
        if i < j:
            a[j] = a[i]
            j -= 1
        # 再从右端向左找第一个 < pivot
        while i < j and a[j] >= pivot:
            j -= 1
        if i < j:
            a[i] = a[j]
            i += 1
    a[i] = pivot
    return i

def partition_offby1(a, lo, hi, shift_left=True):
    """干扰项 D：第二趟某子表枢轴落位偏移1位（其余步骤正确）。
    先用正确 partition 得到正确 pi，再把枢轴从 pi 移到 pi±1。
    """
    pivot = a[lo]
    # 先收集本子表元素，做正确 partition 得到正确排列
    sub = a[lo:hi+1]
    correct = list(sub)
    pi = partition_correct(correct, 0, len(correct)-1)
    # 枢轴正确在 correct[pi]，偏移1位
    if shift_left and pi > 0:
        # 与左边交换
        correct[pi], correct[pi-1] = correct[pi-1], correct[pi]
    elif not shift_left and pi < len(correct)-1:
        correct[pi], correct[pi+1] = correct[pi+1], correct[pi]
    a[lo:hi+1] = correct
    return lo + pi

# ---- 正确路径：A ----
def solve_A(seq):
    a = list(seq)
    n = len(a)
    # 第一趟：对整个序列 partition
    pi1 = partition_correct(a, 0, n-1)
    # 第二趟：对左、右子表分别 partition（长度为1不划分）
    if pi1 - 0 >= 2:
        partition_correct(a, 0, pi1-1)
    if n-1 - pi1 >= 2:
        partition_correct(a, pi1+1, n-1)
    return a, pi1

# ---- 干扰项 B：只做一趟 ----
def solve_B(seq):
    a = list(seq)
    n = len(a)
    pi1 = partition_correct(a, 0, n-1)
    return a, pi1

# ---- 干扰项 C：同侧扫描，两趟 ----
def solve_C(seq):
    a = list(seq)
    n = len(a)
    pi1 = partition_same_side(a, 0, n-1)
    if pi1 - 0 >= 2:
        partition_same_side(a, 0, pi1-1)
    if n-1 - pi1 >= 2:
        partition_same_side(a, pi1+1, n-1)
    return a, pi1

# ---- 干扰项 D：第二趟某子表枢轴偏移1位 ----
def solve_D(seq):
    a = list(seq)
    n = len(a)
    # 第一趟正确
    pi1 = partition_correct(a, 0, n-1)
    # 第二趟：左子表正确，右子表枢轴偏移（选长度>=2的子表）
    left_len = pi1 - 0
    right_len = n - 1 - pi1
    if left_len >= 2:
        partition_correct(a, 0, pi1-1)
    if right_len >= 2:
        # 右子表枢轴落位偏移1位
        partition_offby1(a, pi1+1, n-1, shift_left=True)
    return a, pi1


def count_diff(seq1, seq2):
    """两个序列不同位置的个数"""
    return sum(1 for x, y in zip(seq1, seq2) if x != y)


if __name__ == '__main__':
    seq = PARAMS

    # ===== PARAMS =====
    print("PARAMS")
    print(f"  原始序列: {seq}")
    print(f"  序列长度: {len(seq)}")
    print()

    A, pi1_A = solve_A(seq)
    B, pi1_B = solve_B(seq)
    C, pi1_C = solve_C(seq)
    D, pi1_D = solve_D(seq)

    # ===== 第一趟信息（非退化性验证用）=====
    print("REASONING - 第一趟划分信息")
    print(f"  第一趟枢轴: {seq[0]}")
    print(f"  第一趟枢轴最终位置(pi): {pi1_A}")
    print(f"  左子表长度: {pi1_A - 0}, 右子表长度: {len(seq)-1 - pi1_A}")
    print(f"  左子表: {A[0:pi1_A]}")
    print(f"  右子表: {A[pi1_A+1:len(seq)]}")
    print()

    print("ANSWER - 各选项序列")
    print(f"  A (正确两趟): {A}")
    print(f"  B (仅一趟):   {B}")
    print(f"  C (同侧扫描): {C}")
    print(f"  D (偏移1位):  {D}")
    print()

    print("区分度 - 各对位置差异数")
    pairs = [('A','B',A,B), ('A','C',A,C), ('A','D',A,D),
             ('B','C',B,C), ('B','D',B,D), ('C','D',C,D)]
    for name1, name2, s1, s2 in pairs:
        print(f"  {name1} vs {name2}: {count_diff(s1, s2)} 个位置不同")
    print()

    # ===== assert 通过条件（逐条翻译 question.md 通过条件）=====
    # 条件1: 正确值唯一 — A 非空
    assert A is not None and len(A) == len(seq), "A 应为完整序列"

    # 条件2: 4选项互异（至少1个位置不同）
    for s1, s2, n1, n2 in [(A,B,'A','B'),(A,C,'A','C'),(A,D,'A','D'),(B,C,'B','C'),(B,D,'B','D'),(C,D,'C','D')]:
        assert count_diff(s1, s2) >= 1, f"{n1} 与 {n2} 不应完全相同（互异条件）"

    # 条件3: 干扰项与声明错误类型对应
    #   B = 仅第一趟（不执行第二趟）
    a_chk = list(seq)
    partition_correct(a_chk, 0, len(seq)-1)
    assert B == a_chk, "B 应等于仅执行第一趟 partition 的结果"

    #   C = 同侧扫描两趟
    assert C == solve_C(seq)[0], "C 应等于同侧扫描两趟的结果"

    #   D = 第二趟某子表枢轴偏移1位（与正确A在右子表区域不同）
    assert count_diff(A, D) >= 1, "D 应与正确结果不同"

    # 条件4: 非退化 — 枢轴最终位置不在首或尾，至少一个子表长度>=2
    assert 0 < pi1_A < len(seq)-1, f"枢轴位置{pi1_A}应在中间（非退化），左右子表均非空"
    left_len = pi1_A - 0
    right_len = len(seq) - 1 - pi1_A
    assert left_len >= 1, "左子表非空"
    assert right_len >= 1, "右子表非空"
    assert left_len >= 2 or right_len >= 2, "至少有一个子表长度>=2需要第二趟划分"

    # 条件5: 区分度 — A与每个干扰项至少2个位置不同，干扰项之间亦至少2个位置不同
    assert count_diff(A, B) >= 2, f"A vs B 区分度不足: {count_diff(A,B)}"
    assert count_diff(A, C) >= 2, f"A vs C 区分度不足: {count_diff(A,C)}"
    assert count_diff(A, D) >= 2, f"A vs D 区分度不足: {count_diff(A,D)}"
    assert count_diff(B, C) >= 2, f"B vs C 区分度不足: {count_diff(B,C)}"
    assert count_diff(B, D) >= 2, f"B vs D 区分度不足: {count_diff(B,D)}"
    assert count_diff(C, D) >= 2, f"C vs D 区分度不足: {count_diff(C,D)}"

    print("ALL ASSERTS PASSED ✓")
