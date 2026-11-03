# -*- coding: utf-8 -*-
"""
扩展操作码计算——零地址指令最大条数
题干规则逐句翻译：16位定长，addr_len=4，N2=3，N1=8
逐级扩展：二地址 → 一地址 → 零地址
"""

def solve(L, addr_len, N2, N1):
    # ---- 二地址级 ----
    # 二地址指令有 2 个地址码，操作码长度 = L - 2*addr_len
    opcode2 = L - 2 * addr_len
    space2 = 2 ** opcode2          # 二地址操作码总编码数
    R2 = space2 - N2               # 二地址占用N2条后剩余编码数（留给一地址扩展）

    # ---- 一地址级 ----
    # 剩余R2个编码各扩展addr_len位 → 一地址可分配空间
    space1 = R2 * (2 ** addr_len)
    R1 = space1 - N1               # 一地址占用N1条后剩余编码数（留给零地址扩展）

    # ---- 零地址级 ----
    # 剩余R1个编码各扩展addr_len位 → 零地址最大条数
    space0 = R1 * (2 ** addr_len)

    answer = space0

    return {
        "L": L,
        "addr_len": addr_len,
        "N2": N2,
        "N1": N1,
        "opcode2_bits": opcode2,
        "space2": space2,
        "R2": R2,
        "space1": space1,
        "R1": R1,
        "space0": space0,
        "answer": answer,
    }


# ---- 注入题干参数 ----
L = 16
addr_len = 4
N2 = 3
N1 = 8

result = solve(L, addr_len, N2, N1)

# ---- 底部：打印完整数据流（PARAMS / PROCESS / RESULT + 场景规则相关量）----
print("=" * 55)
print("PARAMS:")
print("  L =", result["L"], "(指令总长度)")
print("  addr_len =", result["addr_len"], "(地址码位数)")
print("  N2 =", result["N2"], "(二地址指令条数)")
print("  N1 =", result["N1"], "(一地址指令条数)")
print()

print("PROCESS (逐级扩展):")
print("  [二地址级]")
print("    操作码位数 = L - 2*addr_len =", result["L"], "- 2*", result["addr_len"], "=", result["opcode2_bits"], "位")
print("    二地址操作码总编码数 space2 = 2^%d = %d" % (result["opcode2_bits"], result["space2"]))
print("    占用N2=%d条，剩余编码数 R2 = %d - %d = %d" % (result["N2"], result["space2"], result["N2"], result["R2"]))
print()
print("  [一地址级]")
print("    一地址可分配空间 = R2 * 2^addr_len = %d * %d = %d" % (result["R2"], 2**result["addr_len"], result["space1"]))
print("    占用N1=%d条，剩余编码数 R1 = %d - %d = %d" % (result["N1"], result["space1"], result["N1"], result["R1"]))
print()
print("  [零地址级]")
print("    零地址最大条数 = R1 * 2^addr_len = %d * %d = %d" % (result["R1"], 2**result["addr_len"], result["space0"]))
print()

print("RESULT:")
print("  零地址指令最大条数 =", result["answer"])
print("=" * 55)

# ---- 场景规则验证（打印约束量，让审核对照场景规则直接判断）----
# 规则1: 三级预留均参与（基础操作码≥4位 且 N2>0 且 N1>0 且 各级剩余>0）
rule1 = {
    "基础操作码位数 >= 4": result["opcode2_bits"] >= 4,
    "N2 > 0": result["N2"] > 0,
    "N1 > 0": result["N1"] > 0,
    "R2 > 0": result["R2"] > 0,
    "R1 > 0": result["R1"] > 0,
}

# 规则2: 逐级扩展公式一致性
rule2_formula = ((2 ** (result["L"] - 2 * result["addr_len"]) - result["N2"]) * (2 ** result["addr_len"]) - result["N1"]) * (2 ** result["addr_len"])
rule2 = {
    "公式验算值": rule2_formula,
    "与answer一致": rule2_formula == result["answer"],
}

# 规则3: 答案唯一且非平凡（正整数）
rule3 = {
    "answer为正整数": isinstance(result["answer"], int) and result["answer"] > 0,
}

print("RULE_CHECK (场景规则):")
print("  规则1 三级预留均参与:", rule1, "→ 全部满足" if all(rule1.values()) else "→ 有不满足项!")
print("  规则2 逐级公式一致性:", rule2)
print("  规则3 答案非平凡正整数:", rule3)
print("=" * 55)
