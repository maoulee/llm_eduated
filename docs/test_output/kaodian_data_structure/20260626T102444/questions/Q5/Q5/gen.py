# -*- coding: utf-8 -*-
"""
题目：二叉树叶子结点数与度为2结点数的关系应用
n = 18, n2 = 7, 求 n0
公式：n0 = n2 + 1
"""

# ============ PARAMS ============
n = 18
n2 = 7
# ============ /PARAMS ============

def solve_correct(n2):
    """正确路径：n0 = n2 + 1"""
    return n2 + 1

def solve_formula_reversed(n2):
    """错误路径B：公式记反 n0 = n2 - 1"""
    return n2 - 1

def solve_ignore_n1(n, n2):
    """错误路径C：忽略 n1，直接 n0 = n - n2"""
    return n - n2

def solve_confuse_n2(n2):
    """错误路径D：叶子与度为2结点混淆，取 n2"""
    return n2

# 计算各选项
A = solve_correct(n2)       # 正确值
B = solve_formula_reversed(n2)  # 公式记反
C = solve_ignore_n1(n, n2)  # 忽略 n1
D = solve_confuse_n2(n2)    # 混淆 n2

# 一致性：求 n1 并校验
n0 = A
n1 = n - n0 - n2

# ============ REASONING ============
print("=== REASONING ===")
print(f"参数：n = {n}, n2 = {n2}")
print(f"二叉树性质公式：n0 = n2 + 1 = {n2} + 1 = {n0}")
print(f"验证一致性：n = n0 + n1 + n2 => {n} = {n0} + n1 + {n2} => n1 = {n1}")
print(f"n1 = {n1} >= 0，参数一致")
print()
print(f"A（正确）: n0 = n2 + 1 = {A}")
print(f"B（公式记反）: n0 = n2 - 1 = {B}")
print(f"C（忽略n1）: n0 = n - n2 = {C}")
print(f"D（混淆n2）: n0 = n2 = {D}")
# ============ /REASONING ============

# ============ ANSWER ============
print()
print("=== ANSWER ===")
print(f"A = {A}")
print(f"B = {B}")
print(f"C = {C}")
print(f"D = {D}")
print(f"正确答案：A = {A}")
# ============ /ANSWER ============

# ============ ASSERTS（通过条件 → 代码断言）============
# 条件1：正确值唯一确定，A = n2 + 1 = 8
assert A == 8, f"条件1失败：A 应为 8，实际 {A}"
assert A == n2 + 1, f"条件1失败：A 应等于 n2+1={n2+1}，实际 {A}"

# 条件2：四选项互异，无碰撞
assert len({A, B, C, D}) == 4, f"条件2失败：四选项不互异，A={A}, B={B}, C={C}, D={D}"

# 条件2细化：各干扰项精确对应声明值
assert B == n2 - 1, f"B 应为 n2-1={n2-1}，实际 {B}"
assert C == n - n2, f"C 应为 n-n2={n-n2}，实际 {C}"
assert D == n2, f"D 应为 n2={n2}，实际 {D}"

# 条件3：干扰项对应声明错误类型（B/C/D 各来自不同错误路径函数）
assert B == solve_formula_reversed(n2), "B 未由公式记反路径产出"
assert C == solve_ignore_n1(n, n2), "C 未由忽略n1路径产出"
assert D == solve_confuse_n2(n2), "D 未由混淆n2路径产出"

# 条件4：干扰项合理性（落在合理范围，彼此可区分）
for val in [A, B, C, D]:
    assert 0 < val < n, f"干扰项 {val} 不在合理范围 (0, {n})"

# 条件5：一致性校验 n = n0 + n1 + n2，n1 >= 0
assert n == n0 + n1 + n2, f"条件5失败：{n} != {n0} + {n1} + {n2}"
assert n1 >= 0, f"条件5失败：n1 = {n1} < 0"

print()
print("=== ALL ASSERTS PASSED ===")
