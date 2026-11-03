# -*- coding: utf-8 -*-
"""
扩展操作码数量计算 — 代码翻译
题干规则 → Python 模型，底部打印完整数据流 + assert 逐条验证场景规则。
"""

def solve(L, A, N):
    # ---- 翻译：各级操作码位数 = L - Σ地址码位数 ----
    opcode_2 = L - 2 * A          # 二地址操作码位数
    opcode_1 = L - A              # 一地址操作码位数
    opcode_0 = L                  # 零地址操作码位数

    # ---- 翻译：二地址级保留的扩展前缀数 ----
    R1 = (1 << opcode_2) - N      # 2^opcode_2 种编码中，扣除已用的 N 条二地址指令

    # ---- 翻译：一地址编码空间 = R1 × 2^(opcode_1-opcode_2) ----
    one_addr_space = R1 * (1 << (opcode_1 - opcode_2))

    # ---- 翻译：为支持零地址扩展，一地址级至少保留 1 个前缀 ----
    R2_min = 1

    # ---- 翻译：一地址指令最大条数 = 编码空间 - 保留前缀 ----
    max1 = one_addr_space - R2_min

    # ---- 翻译：零地址指令最大条数 = R2 × 2^(opcode_0-opcode_1) ----
    max0 = R2_min * (1 << (opcode_0 - opcode_1))

    return {
        "L": L, "A": A, "N": N,
        "opcode_2": opcode_2,
        "opcode_1": opcode_1,
        "opcode_0": opcode_0,
        "R1": R1,
        "one_addr_space": one_addr_space,
        "R2_min": R2_min,
        "max1": max1,
        "max0": max0,
    }


def main():
    L, A, N = 16, 4, 6
    r = solve(L, A, N)

    # ---- 底部：打印完整数据流 ----
    print("=" * 60)
    print("PARAMS:", {"L": r["L"], "A": r["A"], "N": r["N"]})
    print("-" * 60)
    print("PROCESS:")
    print("  opcode_2 (二地址操作码位数 = L-2A)  =", r["opcode_2"])
    print("  opcode_1 (一地址操作码位数 = L-A )  =", r["opcode_1"])
    print("  opcode_0 (零地址操作码位数 = L    )  =", r["opcode_0"])
    print("  R1   (二地址保留前缀 = 2^op2 - N)   =", r["R1"],
          " [ 2^%d - %d ]" % (r["opcode_2"], r["N"]))
    print("  one_addr_space (R1*2^A)             =", r["one_addr_space"])
    print("  R2_min (一地址至少保留前缀)          =", r["R2_min"])
    print("  max1 (一地址最大条数 = space-R2)     =", r["max1"])
    print("  max0 (零地址最大条数 = R2*2^A)       =", r["max0"])
    print("=" * 60)
    print("RESULT:")
    print("  Q1(a) 一地址操作码位数 =", r["opcode_1"])
    print("  Q1(b) 一地址最大条数   =", r["max1"])
    print("  Q1(c) 至少保留前缀数   =", r["R2_min"])
    print("  Q2    零地址最大条数   =", r["max0"])
    print("=" * 60)

    # ---- assert：逐条验证场景规则（约束清单 1-7）----
    # 约束 1：位数守恒
    assert r["opcode_2"] + 2 * r["A"] == r["L"], "位数守恒: opcode_2+2A==L"
    assert r["opcode_1"] + r["A"] == r["L"],      "位数守恒: opcode_1+A==L"
    assert r["opcode_0"] + 0 == r["L"],           "位数守恒: opcode_0==L"

    # 约束 2：扩展前缀递推
    assert r["R1"] == (1 << r["opcode_2"]) - r["N"], "R1==2^opcode_2-N"
    assert r["R1"] > 0, "R1>0 确保有扩展空间"

    # 约束 3：一地址编码空间
    assert r["one_addr_space"] == r["R1"] * (1 << (r["opcode_1"] - r["opcode_2"])), \
        "one_addr_space==R1*2^(opcode_1-opcode_2)"
    assert r["opcode_1"] - r["opcode_2"] == r["A"], "opcode_1-opcode_2==A"

    # 约束 4：R2 最小值为 1
    assert r["R2_min"] == 1, "R2_min==1"

    # 约束 5：一地址最大条数
    assert r["max1"] == r["one_addr_space"] - r["R2_min"], "max1==one_addr_space-R2_min"

    # 约束 6：零地址最大条数
    assert r["max0"] == r["R2_min"] * (1 << (r["opcode_0"] - r["opcode_1"])), \
        "max0==R2_min*2^(opcode_0-opcode_1)"
    assert r["opcode_0"] - r["opcode_1"] == r["A"], "opcode_0-opcode_1==A"

    # 约束 7：答案非平凡
    assert r["max1"] > 0 and r["max0"] > 0, "max1>0 且 max0>0"

    print("\n>>> 所有 assert 通过，场景规则验证完毕。")


if __name__ == "__main__":
    main()
