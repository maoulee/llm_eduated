def solve(n, n1):
    """
    二叉树性质：n0 = n2 + 1，n = n0 + n1 + n2
    联立求解 n0（叶子结点数）
    """
    # n = n0 + n1 + n2, n0 = n2 + 1
    # => n = (n2 + 1) + n1 + n2 = 2*n2 + 1 + n1
    # => n2 = (n - n1 - 1) / 2
    # => n0 = n2 + 1 = (n - n1 + 1) / 2
    n0 = (n - n1 + 1) // 2
    n2 = n0 - 1
    return n0, n1, n2


def solve_error_B(n, n1):
    """干扰项B：公式方向记反，误用 n2 = n0 + 1"""
    # n = n0 + n1 + n2, 误用 n2 = n0 + 1
    # => n = n0 + n1 + (n0 + 1) = 2*n0 + n1 + 1
    # => n0 = (n - n1 - 1) / 2
    n0 = (n - n1 - 1) // 2
    return n0


def solve_error_C(n, n1):
    """干扰项C：概念混淆，将 n1 当作 n0"""
    return n1


def solve_error_D(n, n1):
    """干扰项D：错误认为 n2 = n - n1，再套用 n0 = n2 + 1"""
    n2 = n - n1
    n0 = n2 + 1
    return n0


# 注入参数
n = 23
n1 = 0

# 正确求解
n0, n1_out, n2 = solve(n, n1)
print(f"正确解：n0={n0}, n1={n1_out}, n2={n2}")
print(f"验证：n0+n1+n2 = {n0+n1_out+n2} == n={n}")

# 干扰项
B = solve_error_B(n, n1)
C = solve_error_C(n, n1)
D = solve_error_D(n, n1)
print(f"干扰项 B={B}, C={C}, D={D}")

# ===== 验证段：翻译「通过条件」为 assert =====

# 条件1：正确值唯一确定，n0=12
assert n0 == 12, f"正确值应为12，实际{n0}"

# 条件2：4选项互异
A = n0
assert len({A, B, C, D}) == 4, f"选项不互异: A={A}, B={B}, C={C}, D={D}"

# 条件3：干扰项对应错误类型
assert B == 11, f"B应为11（公式记反），实际{B}"
assert C == 0, f"C应为0（n1当n0），实际{C}"
assert D == 24, f"D应为24（n2=n-n1再+1），实际{D}"

# 条件4：干扰项有合理性（非负整数，在合理范围内）
assert all(isinstance(v, int) and v >= 0 for v in [A, B, C, D]), "干扰项应为非负整数"

# 一致性验证
assert n0 + n1_out + n2 == n, "结点总数不一致"
assert n0 == n2 + 1, "二叉树性质 n0=n2+1 不满足"

print("\n所有验证通过 ✓")
print(f"\n最终选项：A={A}, B={B}, C={C}, D={D}")
