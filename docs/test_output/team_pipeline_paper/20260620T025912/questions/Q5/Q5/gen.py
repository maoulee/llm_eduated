# 二叉树结点性质计算题 - gen.py

# 题干参数
n = 831    # 总结点数
n1 = 30    # 度为1的结点数

# ========== 正确解法 ==========
# n0 = n2 + 1, n = n0 + n1 + n2
# => n = (n2+1) + n1 + n2 = 2*n2 + n1 + 1
# => n2 = (n - n1 - 1) / 2
# => n0 = n2 + 1
n2_correct = (n - n1 - 1) // 2
n0_correct = n2_correct + 1

print(f"PARAMS: n={n}, n1={n1}")
print(f"REASONING: n2 = (n - n1 - 1) / 2 = ({n} - {n1} - 1) / 2 = {n2_correct}")
print(f"REASONING: n0 = n2 + 1 = {n2_correct} + 1 = {n0_correct}")
print(f"ANSWER: {n0_correct}")

# ========== 干扰项计算 ==========
# B: 公式记反，误用 n2 = n0 + 1
# n = n0 + n1 + n2 = n0 + n1 + (n0 + 1) = 2*n0 + n1 + 1
# => n0 = (n - n1 - 1) / 2
n0_B = (n - n1 - 1) // 2

# C: 误用完全二叉树性质，假设 n1 = 0
# n = n0 + n2 = n0 + (n0 - 1) = 2*n0 - 1
# => n0 = (n + 1) / 2
n0_C = (n + 1) // 2

# D: 混淆公式，误认为 n0 = n1 + 1
n0_D = n1 + 1

print(f"OPTION_A: {n0_correct}")
print(f"OPTION_B: {n0_B}")
print(f"OPTION_C: {n0_C}")
print(f"OPTION_D: {n0_D}")

# ========== 验证段（通过条件 → assert） ==========

# 条件1: 4选项互异
A, B, C, D = n0_correct, n0_B, n0_C, n0_D
assert len({A, B, C, D}) == 4, f"选项碰撞: A={A}, B={B}, C={C}, D={D}"

# 条件2: 正确值唯一确定，且等于A
assert A == n0_correct, "A选项不等于正确值"
# 验证正确解满足原始方程
assert n0_correct + n1 + n2_correct == n, "正确解不满足 n = n0 + n1 + n2"
assert n0_correct == n2_correct + 1, "正确解不满足 n0 = n2 + 1"

# 条件3: 干扰项对应声明错误类型
assert B == n0_B, "B选项不等于公式记反的结果"
assert C == n0_C, "C选项不等于误用完全二叉树性质的结果"
assert D == n0_D, "D选项不等于混淆公式的结果"

# 条件4: 干扰项有合理性（均为正整数，非荒谬值）
assert B > 0 and isinstance(B, int), "B选项不合理"
assert C > 0 and isinstance(C, int), "C选项不合理"
assert D > 0 and isinstance(D, int), "D选项不合理"

print("所有验证通过")
