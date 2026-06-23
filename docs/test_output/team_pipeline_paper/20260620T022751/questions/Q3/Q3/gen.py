# 二维数组列优先存储地址计算 - gen.py

def solve(m, n, base, L, i, j):
    """列优先存储地址计算"""
    return base + (j * m + i) * L

def solve_row_major(m, n, base, L, i, j):
    """行优先公式（干扰项A）"""
    return base + (i * n + j) * L

def solve_swapped(m, n, base, L, i, j):
    """行列颠倒（干扰项B）"""
    return base + (i * m + j) * L

def solve_no_L(m, n, base, L, i, j):
    """忘记乘L（干扰项D）"""
    return base + j * m + i

# 参数
m = 5       # 行数
n = 6       # 列数
base = 1000 # 基地址
L = 4       # 元素大小

# 验证已知条件 A[1][2] = 1044
known_i, known_j = 1, 2
known_addr = solve(m, n, base, L, known_i, known_j)
assert known_addr == 1044, f"已知条件不自洽: A[{known_i}][{known_j}] = {known_addr} != 1044"

# 目标 A[2][3]
target_i, target_j = 2, 3

# 计算正确值
correct = solve(m, n, base, L, target_i, target_j)

# 计算干扰项
A_distractor = solve_row_major(m, n, base, L, target_i, target_j)
B_distractor = solve_swapped(m, n, base, L, target_i, target_j)
D_distractor = solve_no_L(m, n, base, L, target_i, target_j)

# 通过条件断言
# 1. 4选项互异
assert len({A_distractor, B_distractor, correct, D_distractor}) == 4, "选项有碰撞"

# 2. 正确值唯一确定且等于选项C
assert correct == 1068, f"正确值计算错误: {correct}"

# 3. 干扰项对应声明错误类型
assert A_distractor == 1060, f"干扰项A错误: {A_distractor}"
assert B_distractor == 1052, f"干扰项B错误: {B_distractor}"
assert D_distractor == 1017, f"干扰项D错误: {D_distractor}"

# 4. 已知条件自洽（已在上面assert）

# 5. 计算结果在合法范围内
assert correct < 65536, f"结果超出范围: {correct}"

# 输出
print(f"PARAMS: m={m}, n={n}, base={base}, L={L}, target=A[{target_i}][{target_j}]")
print(f"REASONING: 列优先公式 base + (j*m + i)*L = {base} + ({target_j}*{m} + {target_i})*{L} = {correct}")
print(f"OPTION_A (行优先误用): {A_distractor}")
print(f"OPTION_B (行列颠倒): {B_distractor}")
print(f"OPTION_C (正确): {correct}")
print(f"OPTION_D (忘记乘L): {D_distractor}")
print(f"ANSWER: C")
