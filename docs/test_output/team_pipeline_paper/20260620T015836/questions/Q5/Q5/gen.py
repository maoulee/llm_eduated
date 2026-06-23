"""
二叉树叶子结点数计算
题干: n=11, n1=4, 求 n0
"""
from fractions import Fraction

n = 11
n1 = 4

# === 正确计算 ===
# n = n0 + n1 + n2,  n0 = n2 + 1
# => n2 = (n - n1 - 1) / 2,  n0 = n2 + 1
n2 = (n - n1 - 1) // 2
n0 = n2 + 1

A = n0  # 正确答案

# === 干扰项 B: 正确求出 n2 后忘记 +1 ===
B = n2

# === 干扰项 C: 误用 n-1 = n1 + n2 (漏乘2) ===
# 错误公式: n - 1 = n1 + n2  =>  n2_wrong = (n - 1 - n1)
#          => n0_wrong = n2_wrong + 1
n2_wrong_C = (n - 1 - n1)
C = n2_wrong_C + 1

# === 干扰项 D: 记成 n0 = n2 - 1 ===
D = n2 - 1

print(f"PARAMS: n={n}, n1={n1}")
print(f"REASONING: n2 = (n - n1 - 1)/2 = ({n} - {n1} - 1)/2 = {n2}")
print(f"REASONING: n0 = n2 + 1 = {n2} + 1 = {n0}")
print(f"REASONING: B = n2 (忘记+1) = {B}")
print(f"REASONING: C: 误用 n-1=n1+n2 -> n2'={n2_wrong_C}, n0'=n2'+1={C}")
print(f"REASONING: D = n2 - 1 (方向记反) = {D}")
print(f"ANSWER: A={A}, B={B}, C={C}, D={D}")

# === 通过条件 assert ===
# 条件1: 参数合法性
assert (n - n1) % 2 == 1, "n - n1 必须为奇数"
assert n2 >= 0 and (n - n1 - 1) % 2 == 0, "n2 必须为非负整数"
assert n0 >= 1, "n0 必须 >= 1"
assert n0 + n1 + n2 == n, "恒等式 n0 + n1 + n2 = n 必须成立"

# 条件2: 4 选项互异
assert len({A, B, C, D}) == 4, f"选项有碰撞: A={A}, B={B}, C={C}, D={D}"

# 条件3: A = 正确值
assert A == n0, "A 必须等于正确值 n0"

# 条件4: 各干扰项对应声明错误类型
assert B == n2, "B 应为正确的 n2（忘记 +1）"
assert C == n2_wrong_C + 1, "C 应为误用公式后的 n0"
assert D == n2 - 1, "D 应为 n2 - 1"

# 条件5: 干扰项合理性（非荒谬值）
for label, val in [("B", B), ("C", C), ("D", D)]:
    assert val >= 0, f"干扰项 {label}={val} 不合理（负值）"

print("ALL ASSERTS PASSED")
