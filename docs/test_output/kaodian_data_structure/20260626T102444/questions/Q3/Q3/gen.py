"""
二维数组列优先存储的地址计算
题干规则翻译：
  列优先公式: LOC(i,j) = base + (j*rows + i) * elem_size
  行优先公式: LOC(i,j) = base + (i*cols + j) * elem_size  （干扰项B）
  下标-1错误: 将 i,j 各减1后代入列优先公式          （干扰项C）
  行列互换错误: 列优先式中 i,j 互换                  （干扰项D）
"""

# ============ 参数 ============
ROWS = 7
COLS = 10
BASE = 200
ELEM_SIZE = 4
I = 3   # 行下标
J = 4   # 列下标

def loc_column_major(base, i, j, rows, elem_size):
    """列优先公式（正确）"""
    return base + (j * rows + i) * elem_size

def loc_row_major(base, i, j, cols, elem_size):
    """行优先公式"""
    return base + (i * cols + j) * elem_size

# ============ 计算各选项 ============

# A: 列优先正确
A = loc_column_major(BASE, I, J, ROWS, ELEM_SIZE)

# B: 行优先公式错误
B = loc_row_major(BASE, I, J, COLS, ELEM_SIZE)

# C: 下标起始约定错误（i-1, j-1 代入列优先公式）
C = loc_column_major(BASE, I - 1, J - 1, ROWS, ELEM_SIZE)

# D: 行列互换错误（列优先式但 i,j 互换: base + (i*rows + j)*elem_size）
D = loc_column_major(BASE, J, I, ROWS, ELEM_SIZE)

# ============ 输出 ============
print("PARAMS:")
print(f"  rows={ROWS}, cols={COLS}, base={BASE}, elem_size={ELEM_SIZE}")
print(f"  target A[{I}][{J}]")
print()
print("REASONING:")
print(f"  A (列优先正确):   LOC = {BASE} + ({J}*{ROWS} + {I})*{ELEM_SIZE}")
print(f"                   = {BASE} + ({J*ROWS} + {I})*{ELEM_SIZE}")
print(f"                   = {BASE} + {J*ROWS + I}*{ELEM_SIZE}")
print(f"                   = {A}")
print(f"  B (行优先错误):   LOC = {BASE} + ({I}*{COLS} + {J})*{ELEM_SIZE}")
print(f"                   = {BASE} + ({I*COLS + J})*{ELEM_SIZE}")
print(f"                   = {B}")
print(f"  C (下标-1错误):   LOC = {BASE} + ({J-1}*{ROWS} + {I-1})*{ELEM_SIZE}")
print(f"                   = {BASE} + ({(J-1)*ROWS} + {I-1})*{ELEM_SIZE}")
print(f"                   = {C}")
print(f"  D (行列互换错误): LOC = {BASE} + ({I}*{ROWS} + {J})*{ELEM_SIZE}")
print(f"                   = {BASE} + ({I*ROWS} + {J})*{ELEM_SIZE}")
print(f"                   = {D}")
print()
print("ANSWER:")
print(f"  A = {A}")
print(f"  B = {B}")
print(f"  C = {C}")
print(f"  D = {D}")

# ============ assert 通过条件 ============

# 条件1: 正确值唯一确定 — A 恰为列优先公式代入结果
assert A == BASE + (J * ROWS + I) * ELEM_SIZE, "A 不是列优先公式正确值"

# 条件2: 四选项互异
assert len({A, B, C, D}) == 4, f"四选项不互异: A={A}, B={B}, C={C}, D={D}"

# 条件3: 干扰项对应声明错误类型
assert B == BASE + (I * COLS + J) * ELEM_SIZE, "B 不是行优先公式结果"
assert C == BASE + ((J - 1) * ROWS + (I - 1)) * ELEM_SIZE, "C 不是下标-1列优先结果"
assert D == BASE + (I * ROWS + J) * ELEM_SIZE, "D 不是行列互换结果"

# 条件4: 干扰项合理性（非负、与基地址同量级）
for label, val in [("A", A), ("B", B), ("C", C), ("D", D)]:
    assert val >= 0, f"{label}={val} 为负，不合理"
    assert 0 <= val <= 4 * BASE + ROWS * COLS * ELEM_SIZE * 4, f"{label}={val} 超出合理范围"

print("\n所有 assert 通过。")
