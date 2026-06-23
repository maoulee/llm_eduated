# -*- coding: utf-8 -*-
"""
二维数组列优先存储的地址计算
参数（来自 question.md）:
  rows=7, cols=5, base=200, elem_size=4
  目标元素 A[i][j] = A[2][3]（第2行第3列，下标从0起始）
修正原因: 原参数 i=3,j=2 时 j*rows+i = i*cols+j = 17 退化，
         改为 i=2,j=3 使列优先与行优先偏移量不同。
"""

# ---- 参数区 ----
rows = 7
cols = 5
base = 200
elem_size = 4
i = 2   # 行下标
j = 3   # 列下标

# ---- 选项A：列优先（正确）----
# Loc(A[i][j]) = base + (j*rows + i) * elem_size
offset_A = j * rows + i
addr_A = base + offset_A * elem_size

# ---- 选项B：行优先混淆 ----
# base + (i*cols + j) * elem_size
offset_B = i * cols + j
addr_B = base + offset_B * elem_size

# ---- 选项C：下标起始混淆（0起始误作1起始，偏移量差1）----
# 误用 i+1 替代 i（行号多1）
offset_C = j * rows + (i + 1)
addr_C = base + offset_C * elem_size

# ---- 选项D：行列维度代入颠倒 ----
# 列优先公式中 rows 与 cols 互换: base + (j*cols + i) * elem_size
offset_D = j * cols + i
addr_D = base + offset_D * elem_size

# ---- 输出 ----
print("=== PARAMS ===")
print(f"rows={rows}, cols={cols}, base={base}, elem_size={elem_size}")
print(f"target: A[{i}][{j}]")
print()
print("=== REASONING ===")
print(f"列优先偏移: j*rows+i = {j}*{rows}+{i} = {offset_A}")
print(f"行优先偏移: i*cols+j = {i}*{cols}+{j} = {offset_B}")
print(f"下标差1偏移: j*rows+(i+1) = {j}*{rows}+{i+1} = {offset_C}")
print(f"行列颠倒偏移: j*cols+i = {j}*{cols}+{i} = {offset_D}")
print()
print(f"A (列优先,正确): {base} + {offset_A}*{elem_size} = {addr_A}")
print(f"B (行优先):      {base} + {offset_B}*{elem_size} = {addr_B}")
print(f"C (下标差1):     {base} + {offset_C}*{elem_size} = {addr_C}")
print(f"D (行列颠倒):    {base} + {offset_D}*{elem_size} = {addr_D}")
print()
print("=== ANSWER ===")
print(f"A={addr_A}")
print(f"B={addr_B}")
print(f"C={addr_C}")
print(f"D={addr_D}")

# ---- 验证段（翻译通过条件为 assert）----
# 条件6: 偏移量非平凡，列优先与行优先结果不同
assert offset_A != offset_B, f"退化: 列优先偏移={offset_A} == 行优先偏移={offset_B}"

# 条件1: 4选项互异
options = [addr_A, addr_B, addr_C, addr_D]
assert len(set(options)) == 4, f"选项碰撞: {options}"

# 条件2: A=正确值（列优先公式）
assert addr_A == base + (j * rows + i) * elem_size

# 条件3: 干扰项对应声明错误类型
assert addr_B == base + (i * cols + j) * elem_size, "B应为行优先结果"
assert addr_C == base + (j * rows + (i + 1)) * elem_size, "C应为下标差1结果"
assert addr_D == base + (j * cols + i) * elem_size, "D应为行列颠倒结果"

# 条件5: 选项间距 >= elem_size
from itertools import combinations
for a, b in combinations(options, 2):
    assert abs(a - b) >= elem_size, f"间距不足: |{a}-{b}|={abs(a-b)} < {elem_size}"

# 条件6补充: 偏移量 > 0
assert offset_A > 0, "偏移量应为正"

print()
print("=== ALL ASSERTS PASSED ===")
