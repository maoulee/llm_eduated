"""
扩展操作码编码——零地址指令最大条数计算
题干规则翻译：逐级扩展链（剩余前缀 → ×2^a 扩展 → −本级条数 → 得下级剩余）
底部 print 完整数据流，供审核对照场景规则验证。
"""


def solve(L=16, a=4, N2=200, N1=500):
    """翻译题干逐级扩展链，返回各级中间值与 N0_max。"""

    # --- 三地址级（背景：操作码位数） ---
    op3_bits = L - 3 * a               # 三地址操作码位数 = 16 - 12 = 4
    three_addr_max = 2 ** op3_bits     # 三地址编码空间 = 2^4 = 16（已占满）

    # --- 二地址级 ---
    two_addr_space = 2 ** (L - 2 * a)  # 二地址编码空间 = 2^8 = 256
    remaining_prefix1 = two_addr_space - N2   # 剩余前缀1 = 256 - 200 = 56

    # --- 一地址级 ---
    one_addr_space = remaining_prefix1 * (2 ** a)  # 一地址空间 = 56 × 16 = 896
    remaining_prefix2 = one_addr_space - N1         # 剩余前缀2 = 896 - 500 = 396

    # --- 零地址级 ---
    zero_addr_max = remaining_prefix2 * (2 ** a)    # N0_max = 396 × 16 = 6336

    return {
        "L": L, "a": a,
        "op3_bits": op3_bits,
        "three_addr_max": three_addr_max,
        "two_addr_space": two_addr_space,
        "N2": N2,
        "remaining_prefix1": remaining_prefix1,
        "one_addr_space": one_addr_space,
        "N1": N1,
        "remaining_prefix2": remaining_prefix2,
        "N0_max": zero_addr_max,
    }


def solve_q3(N2_new=210):
    """Q3：N2 增至 210，返回新 N0_max 及各级剩余前缀。"""
    r = solve(N2=N2_new)
    return r["N0_max"], r["remaining_prefix1"], r["remaining_prefix2"]


# ===================== 主流程 =====================
result = solve()

# ===== 场景规则 assert（约束可机检，打到特征，禁弱化/禁恒真）=====
L, a = result["L"], result["a"]
N2, N1 = result["N2"], result["N1"]
remaining_prefix1 = result["remaining_prefix1"]
remaining_prefix2 = result["remaining_prefix2"]
N0_max = result["N0_max"]

assert N2 < 2 ** (L - 2 * a), "N2 超过二地址编码空间"
assert remaining_prefix1 > 0, "剩余前缀1 <= 0，无法扩展到一地址"
assert remaining_prefix2 > 0, "剩余前缀2 <= 0，无法扩展到零地址"
assert N0_max == remaining_prefix2 * (2 ** a), "N0_max ≠ 剩余前缀2 × 2^a"
assert N0_max == ((2 ** (L - 2 * a) - N2) * (2 ** a) - N1) * (2 ** a), "N0_max 公式不符"
assert remaining_prefix1 & (remaining_prefix1 - 1) != 0, "剩余前缀1 是2的幂（平凡退化）"
assert remaining_prefix2 & (remaining_prefix2 - 1) != 0, "剩余前缀2 是2的幂（平凡退化）"

# ===== Q3 计算 =====
N0_max_q3, rem1_q3, rem2_q3 = solve_q3(N2_new=210)

# ===================== 底部数据流 =====================
print("=" * 60)
print("PARAMS:")
print("  指令字长 L =", L, "位")
print("  每个地址码位数 a =", a, "位")
print("  三地址指令: 占满其编码空间（2^{} = {} 条）".format(result["op3_bits"], result["three_addr_max"]))
print("  二地址指令条数 N2 =", N2)
print("  一地址指令条数 N1 =", N1)
print()

print("PROCESS — 逐级扩展链:")
print("  【三地址级】")
print("    三地址操作码位数 = L - 3a = {} - {} = {} 位".format(L, 3*a, result["op3_bits"]))
print("    三地址编码空间 = 2^{} = {}".format(result["op3_bits"], result["three_addr_max"]))
print("    三地址指令占满全部 {} 个编码 → 进入二地址扩展".format(result["three_addr_max"]))
print()
print("  【二地址级】")
print("    二地址操作码空间 = 2^(L-2a) = 2^{} = {}".format(L - 2*a, result["two_addr_space"]))
print("    二地址指令占用 N2 = {} 条".format(N2))
print("    剩余前缀1 = {} - {} = {}".format(result["two_addr_space"], N2, remaining_prefix1))
print("    (剩余前缀1 > 0, 不为2的幂)")
print()
print("  【一地址级】")
print("    一地址指令空间 = 剩余前缀1 × 2^a = {} × {} = {}".format(remaining_prefix1, 2**a, result["one_addr_space"]))
print("    一地址指令占用 N1 = {} 条".format(N1))
print("    剩余前缀2 = {} - {} = {}".format(result["one_addr_space"], N1, remaining_prefix2))
print("    (剩余前缀2 > 0, 不为2的幂)")
print()
print("  【零地址级】")
print("    零地址最大条数 N0_max = 剩余前缀2 × 2^a = {} × {} = {}".format(remaining_prefix2, 2**a, N0_max))
print()

print("RESULT:")
print("  零地址指令最大条数 N0_max =", N0_max)
print()

print("RULE_CHECK（场景规则可读验证）:")
print("  N2 < 2^(L-2a): {} < {} → {}".format(N2, 2**(L-2*a), N2 < 2**(L-2*a)))
print("  剩余前缀1 > 0: {} > 0 → {}".format(remaining_prefix1, remaining_prefix1 > 0))
print("  剩余前缀2 > 0: {} > 0 → {}".format(remaining_prefix2, remaining_prefix2 > 0))
print("  N0_max == 剩余前缀2 × 2^a: {} == {} → {}".format(N0_max, remaining_prefix2*(2**a), N0_max == remaining_prefix2*(2**a)))
print("  剩余前缀1 非2的幂: {} → {}".format(remaining_prefix1, remaining_prefix1 & (remaining_prefix1-1) != 0))
print("  剩余前缀2 非2的幂: {} → {}".format(remaining_prefix2, remaining_prefix2 & (remaining_prefix2-1) != 0))
print()

print("=" * 60)
print("Q3 — N2 从 200 增至 210:")
print("  剩余前缀1: {} → {} （减少 {}）".format(remaining_prefix1, rem1_q3, remaining_prefix1 - rem1_q3))
print("  剩余前缀2: {} → {} （减少 {}）".format(remaining_prefix2, rem2_q3, remaining_prefix2 - rem2_q3))
print("  N0_max: {} → {} （减少 {}）".format(N0_max, N0_max_q3, N0_max - N0_max_q3))
print("  级联: N2 +10 → 剩余前缀1 -10 → 剩余前缀2 -10×16={} → N0_max -{}×16={}".format(10*(2**a), 10*(2**a), 10*(2**a)*(2**a)))
print("=" * 60)
