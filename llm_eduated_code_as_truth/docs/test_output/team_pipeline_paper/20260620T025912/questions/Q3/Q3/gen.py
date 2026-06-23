# gen.py — 二维数组列优先存储地址计算

# ========== PARAMS ==========
M = 5          # 行数 (0..4)
N = 7          # 列数 (0..6)
L = 4          # 元素大小(字节)
Base = 1000    # 基地址 LOC(A[0][0])
i = 1          # 目标行索引
j = 2          # 目标列索引

# ========== REASONING ==========
# 列优先公式: LOC(A[i][j]) = Base + (j * M + i) * L
correct = Base + (j * M + i) * L

# 干扰项 B: 行优先公式误用 (i * N + j) * L + Base
distractor_B = Base + (i * N + j) * L

# 干扰项 C: m/n 位置颠倒 → 用 N 代替 M 代入列优先公式
distractor_C = Base + (j * N + i) * L

# 干扰项 D: 忘记乘 L → 直接用偏移量加基地址
distractor_D = Base + (j * M + i)

# ========== 验证通过条件 ==========
# 1. 行优先 ≠ 列优先
assert distractor_B != correct, "行优先与列优先结果相同，考点退化"

# 2. 四选项互异
opts = {correct, distractor_B, distractor_C, distractor_D}
assert len(opts) == 4, f"选项碰撞: A={correct}, B={distractor_B}, C={distractor_C}, D={distractor_D}"

# 3. 结果在合理范围
assert correct <= 65536, f"结果超出范围: {correct}"

# 4. 干扰项对应声明错误类型（非随机）
assert distractor_B != correct, "B应≠A"
assert distractor_C != correct, "C应≠A"
assert distractor_D != correct, "D应≠A"

# ========== ANSWER ==========
print(f"PARAMS: M={M}, N={N}, L={L}, Base={Base}, i={i}, j={j}")
print(f"REASONING: 列优先公式 LOC(A[{i}][{j}]) = {Base} + ({j}*{M}+{i})*{L} = {Base} + {j*M+i}*{L} = {correct}")
print(f"ANSWER: {correct}")
print(f"OPTIONS: A={correct}, B={distractor_B}, C={distractor_C}, D={distractor_D}")
