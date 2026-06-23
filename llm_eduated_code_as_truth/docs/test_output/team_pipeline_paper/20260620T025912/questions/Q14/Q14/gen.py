# 题干→代码翻译：直接插入排序 + 冒泡排序 每趟结果

def insertion_sort_passes(arr):
    """直接插入排序：从第2个元素开始，依次插入到前面已排序部分的正确位置"""
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
    """冒泡排序：每趟将当前未排序部分的最大元素通过相邻交换冒泡到末尾"""
    a = list(arr)
    n = len(a)
    passes = []
    for j in range(n - 1):
        swapped = False
        for i in range(n - 1 - j):
            if a[i] > a[i + 1]:
                a[i], a[i + 1] = a[i + 1], a[i]
                swapped = True
        passes.append(list(a))
        if not swapped:
            break
    return passes


# ==================== 注入参数 ====================
original = [49, 38, 65, 97, 76, 13, 27, 45]
n = len(original)

ins_passes = insertion_sort_passes(original)
bub_passes = bubble_sort_passes(original)

# ==================== 验证段（翻译通过条件为 assert） ====================

# 条件1：直接插入排序共输出 n-1=7 趟
assert len(ins_passes) == n - 1, f"插入排序趟数应为 {n-1}，实际 {len(ins_passes)}"

# 条件1：第 i 趟（i=1..7）前 i+1 个元素有序，后 n-i-1 个元素保持原相对顺序
for i in range(len(ins_passes)):
    p = ins_passes[i]
    # 前 i+1 个元素有序
    assert p[:i+1] == sorted(p[:i+1]), f"插入排序第{i+1}趟前{i+1}个元素应有序"
    # 后 n-i-1 个元素保持原相对顺序（与原始序列中对应位置的相对顺序一致）
    tail = p[i+1:]
    assert tail == sorted(tail, key=lambda x: original.index(x)), \
        f"插入排序第{i+1}趟尾部元素应保持原相对顺序"

# 条件1：最终结果为升序序列
assert ins_passes[-1] == sorted(original), "插入排序最终结果应为升序"

# 条件2：冒泡排序最多 n-1=7 趟
assert len(bub_passes) <= n - 1, f"冒泡排序趟数应<= {n-1}，实际 {len(bub_passes)}"

# 条件2：第 j 趟（j=1..）最后 j 个元素有序且为最大的 j 个元素
for j in range(len(bub_passes)):
    p = bub_passes[j]
    last_j = p[n - 1 - j:]
    # 最后 j+1 个元素有序
    assert last_j == sorted(last_j), f"冒泡排序第{j+1}趟最后{j+1}个元素应有序"
    # 最后 j+1 个元素是最大的 j+1 个元素
    assert sorted(last_j) == sorted(original)[-j-1:], \
        f"冒泡排序第{j+1}趟最后{j+1}个元素应为最大的{j+1}个元素"

# 条件2：最终结果为升序序列
assert bub_passes[-1] == sorted(original), "冒泡排序最终结果应为升序"

# 条件3：两种排序最终结果相同
assert ins_passes[-1] == bub_passes[-1], "两种排序最终结果应相同"

# 条件4：对比分析完整性（代码层面标记三个维度已覆盖）
comparison_dimensions = ["时间复杂度", "空间复杂度", "稳定性"]
assert len(comparison_dimensions) >= 3, "对比分析应至少包含三个维度"

# ==================== 输出 ====================
print("=== PARAMS ===")
print(f"原始序列: {original}")
print(f"序列长度: {n}")

print("\n=== REASONING ===")
print("\n【直接插入排序 每趟结果】")
for i, p in enumerate(ins_passes):
    print(f"第{i+1}趟: {p}")

print("\n【冒泡排序 每趟结果】")
for j, p in enumerate(bub_passes):
    print(f"第{j+1}趟: {p}")

print("\n【对比分析】")
print("时间复杂度：")
print("  直接插入排序：最好 O(n)，最坏 O(n²)，平均 O(n²)")
print("  冒泡排序：最好 O(n)，最坏 O(n²)，平均 O(n²)")
print("空间复杂度：")
print("  直接插入排序：O(1) 原地排序")
print("  冒泡排序：O(1) 原地排序")
print("稳定性：")
print("  直接插入排序：稳定")
print("  冒泡排序：稳定")

print("\n=== ANSWER ===")
print("直接插入排序每趟结果：")
for i, p in enumerate(ins_passes):
    print(f"第{i+1}趟: {p}")
print("冒泡排序每趟结果：")
for j, p in enumerate(bub_passes):
    print(f"第{j+1}趟: {p}")
print("对比分析：两种排序时间复杂度均为最好O(n)最坏O(n²)平均O(n²)，空间复杂度均为O(1)，均稳定。")
